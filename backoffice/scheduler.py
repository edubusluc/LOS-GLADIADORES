"""
Lanzador de procesos programados. `python manage.py run_scheduler` debe ejecutarse
cada minuto (cron, systemd timer o el programador del hosting); en cada pasada
lanza los procesos a los que les toca y los pedidos con "Ejecutar ahora".
"""
import asyncio
import datetime
import io
import logging
import threading
import time
import traceback
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connections as db_connections
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _

from core.emails import build_email

from .cron import Cron
from .jobs import JOBS, SCHEDULER_TIME_ZONE
from .models import JobRun, ScheduledJob

logger = logging.getLogger(__name__)

# Guardamos como mucho esto de la salida de cada ejecución.
MAX_OUTPUT = 20_000
# Si el lanzador no ha pasado en este tiempo, el back-office avisa de que no está en marcha.
LATE_AFTER = datetime.timedelta(minutes=10)
# Cada cuánto da señales de vida una ejecución en marcha y cuánto tiempo sin ellas hace
# falta para darla por muerta. Una ejecución viva nunca se libera, dure lo que dure: si
# se liberase, el lanzador arrancaría otra copia mientras la primera sigue trabajando.
HEARTBEAT_EVERY = 60
HEARTBEAT_STALE_AFTER = datetime.timedelta(minutes=10)


def next_run(spec, after):
    """
    Siguiente ejecución programada (en UTC) posterior a `after`, calculada con la hora de
    SCHEDULER_TIME_ZONE. None si el proceso no tiene horario (solo a mano).
    """
    if not spec.schedule:
        return None  # solo a mano
    local = after.astimezone(ZoneInfo(SCHEDULER_TIME_ZONE))
    return Cron(spec.schedule).next_after(local).astimezone(datetime.timezone.utc)


def sync_jobs(now=None):
    """Crea la fila de estado de los procesos nuevos y calcula su próxima ejecución."""
    now = now or timezone.now()
    for spec in JOBS:
        job, created = ScheduledJob.objects.get_or_create(name=spec.name)
        if (created or job.next_run_at is None) and spec.schedule:
            job.next_run_at = next_run(spec, now)
            job.save(update_fields=["next_run_at"])
    return ScheduledJob.objects.filter(name__in=[s.name for s in JOBS])


def _clip(text):
    """Recorta un texto a MAX_OUTPUT caracteres, indicando cuántos se han quitado."""
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n… (salida recortada, {len(text) - MAX_OUTPUT} caracteres más)"


def _release_stale_locks(now):
    """
    Da por interrumpidas las ejecuciones cuyo proceso ha muerto: las que llevan más de
    HEARTBEAT_STALE_AFTER sin dar señales de vida (p. ej. se reinició el servidor).
    """
    limit = now - HEARTBEAT_STALE_AFTER
    stale = ScheduledJob.objects.filter(running_since__isnull=False).filter(
        Q(heartbeat_at__lt=limit) | Q(heartbeat_at__isnull=True, running_since__lt=limit)
    )
    for job in stale:
        last_seen = job.heartbeat_at or job.running_since
        minutes = int((now - last_seen).total_seconds() // 60)
        job.runs.filter(status=JobRun.RUNNING).update(
            status=JobRun.ERROR, finished_at=now,
            error=f"Interrumpida: el proceso dejó de dar señales de vida hace {minutes} minutos "
                  "(probablemente se reinició o se cayó el servidor).",
        )
        ScheduledJob.objects.filter(pk=job.pk).update(running_since=None, heartbeat_at=None)


class Heartbeat:
    """Hilo que apunta cada HEARTBEAT_EVERY segundos que la ejecución sigue viva."""

    def __init__(self, job, every=HEARTBEAT_EVERY):
        """Prepara el hilo (daemon) que apuntará la señal de vida de `job` cada `every` segundos."""
        self.job = job
        self.every = every
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._beat, name=f"heartbeat-{job.name}", daemon=True)

    def __enter__(self):
        """Arranca el hilo de señales de vida."""
        self.thread.start()
        return self

    def __exit__(self, *exc):
        """Para el hilo y espera a que termine."""
        self.stopped.set()
        self.thread.join()

    def _beat(self):
        """
        Bucle del hilo: actualiza heartbeat_at mientras el proceso siga marcado como en
        ejecución. Al terminar cierra sus conexiones a la base de datos.
        """
        try:
            while not self.stopped.wait(self.every):
                ScheduledJob.objects.filter(pk=self.job.pk, running_since__isnull=False).update(heartbeat_at=timezone.now())
        except Exception:
            logger.exception("No se ha podido apuntar la señal de vida de %s", self.job.name)
        finally:
            db_connections.close_all()


class LiveOutput(io.TextIOBase):
    """
    Salida de un proceso que se va guardando en su JobRun mientras se ejecuta (como mucho
    una vez por segundo), para poder seguirla en directo desde el back-office.
    """

    def __init__(self, run, every=1.0):
        """Salida vacía de `run`, que se guarda como mucho cada `every` segundos."""
        self.run = run
        self.every = every
        self.parts = []
        self.size = 0
        self.saved_at = 0.0
        self.clipped = False

    def writable(self):
        """Siempre se puede escribir (lo exige io.TextIOBase)."""
        return True

    def write(self, text):
        """
        Añade texto a la salida (recortándola en MAX_OUTPUT) y la guarda si ha pasado el
        intervalo desde la última vez.
        """
        if self.clipped or not text:
            return len(text or "")
        if self.size + len(text) > MAX_OUTPUT:
            text = text[:MAX_OUTPUT - self.size] + "\n… (salida recortada)\n"
            self.clipped = True
        self.parts.append(text)
        self.size += len(text)
        if time.monotonic() - self.saved_at >= self.every:
            self.save()
        return len(text)

    def log(self, message):
        """Línea de traza del propio lanzador, con la hora."""
        stamp = timezone.localtime(timezone.now(), ZoneInfo(SCHEDULER_TIME_ZONE)).strftime("%H:%M:%S")
        self.write(f"[{stamp}] {message}\n")

    def getvalue(self):
        """Toda la salida acumulada hasta ahora."""
        return "".join(self.parts)

    def save(self):
        """Guarda la salida acumulada en el JobRun (desde otro hilo si se llama desde código asíncrono)."""
        self.saved_at = time.monotonic()
        if _in_event_loop():
            # Hay procesos que escriben su salida desde código asíncrono (p. ej. Playwright
            # en update_snp_scores), donde Django no deja usar la base de datos: se guarda
            # desde un hilo aparte.
            worker = threading.Thread(target=self._save_in_thread, args=(self.getvalue(),))
            worker.start()
            worker.join()
        else:
            self._save_output(self.getvalue())

    def _save_output(self, output):
        """Escribe la salida en la fila del JobRun sin tocar el resto de campos."""
        JobRun.objects.filter(pk=self.run.pk).update(output=output)

    def _save_in_thread(self, output):
        """Guarda la salida desde un hilo aparte y cierra sus conexiones; un fallo solo se registra."""
        try:
            self._save_output(output)
        except Exception:
            logger.exception("No se ha podido guardar la salida en directo de %s", self.run)
        finally:
            db_connections.close_all()


def _in_event_loop():
    """True si se está dentro de un bucle de asyncio en marcha (ahí Django no deja usar la BD)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def claim_job(job, trigger=JobRun.SCHEDULE, user=None, now=None, args=()):
    """
    Marca el proceso como "en ejecución" y crea su JobRun. Devuelve None si ya estaba en
    marcha (otra pasada del lanzador o de la web lo tiene cogido).
    """
    now = now or timezone.now()
    changes = {"running_since": now, "heartbeat_at": now}
    spec = job.spec
    if trigger == JobRun.SCHEDULE and spec and spec.schedule:
        # La próxima ejecución se calcula ya al empezar: si esta se interrumpe, el lanzador
        # no vuelve a lanzar el proceso hasta su siguiente hora.
        changes["next_run_at"] = next_run(spec, now)
    # Coger el proceso de forma atómica: solo una pasada puede ponerle la marca.
    if not ScheduledJob.objects.filter(pk=job.pk, running_since__isnull=True).update(**changes):
        return None
    return JobRun.objects.create(job=job, trigger=trigger, triggered_by=user, started_at=now, args=list(args))


def execute_run(run):
    """Ejecuta un JobRun ya reclamado, guardando la salida en directo, y libera el proceso."""
    job = run.job
    spec = job.spec
    out = LiveOutput(run)
    started = time.monotonic()
    try:
        if spec is None:
            raise RuntimeError(f"El proceso {job.name} ya no existe en backoffice/jobs.py.")
        args = [*spec.args, *run.args]
        out.log(f"Inicio: python manage.py {' '.join([spec.command, *args])}")
        with Heartbeat(job):
            call_command(spec.command, *args, stdout=out, stderr=out)
        run.status = JobRun.OK
        out.log(f"Fin: correcto en {time.monotonic() - started:.1f} s")
    except BaseException as exc:  # SystemExit/CommandError incluidos: nada debe tumbar el lanzador
        run.status = JobRun.ERROR
        run.error = _clip("".join(traceback.format_exception(exc)))
        out.log(f"Fin: error en {time.monotonic() - started:.1f} s: {exc}")
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        finished = timezone.now()
        run.output = out.getvalue()
        run.finished_at = finished
        run.save()
        changes = {"running_since": None, "heartbeat_at": None, "last_run_at": run.started_at}
        if run.trigger == JobRun.SCHEDULE and spec:
            changes["next_run_at"] = next_run(spec, finished)
        if run.trigger == JobRun.MANUAL:
            changes["run_requested_at"] = None
            changes["run_requested_by"] = None
        ScheduledJob.objects.filter(pk=job.pk).update(**changes)

    if run.status == JobRun.ERROR:
        notify_failure(run)
    return run


def run_job(job, trigger=JobRun.SCHEDULE, user=None, now=None):
    """Reclama y ejecuta un proceso. Devuelve el JobRun, o None si ya estaba en marcha."""
    run = claim_job(job, trigger, user, now)
    return execute_run(run) if run else None


def start_manual_run(job, user, args=()):
    """
    "Ejecutar ahora" desde el back-office: el proceso arranca al momento en segundo plano
    y la página de la ejecución muestra su salida en directo. ``args`` son los datos
    pedidos al lanzarlo (JobSpec.params). Devuelve el JobRun, o None si ya estaba en marcha.
    """
    run = claim_job(job, JobRun.MANUAL, user, args=args)
    if run is None:
        return None
    if getattr(settings, "BACKOFFICE_RUN_JOBS_INLINE", False):  # tests
        execute_run(run)
        return run

    def target():
        """Ejecuta el proceso en el hilo y cierra sus conexiones a la base de datos al terminar."""
        try:
            execute_run(run)
        finally:
            db_connections.close_all()

    threading.Thread(target=target, name=f"job-{job.name}", daemon=True).start()
    return run


def run_due_jobs(now=None):
    """Una pasada del lanzador: lanza lo que toca y lo pedido a mano. Devuelve los JobRun."""
    now = now or timezone.now()
    jobs = sync_jobs(now)
    _release_stale_locks(now)
    runs = []
    due = jobs.filter(running_since__isnull=True).filter(
        Q(run_requested_at__isnull=False) | Q(enabled=True, next_run_at__lte=now)
    )
    for job in list(due):
        manual = job.run_requested_at is not None
        run = run_job(job, JobRun.MANUAL if manual else JobRun.SCHEDULE,
                      user=job.run_requested_by if manual else None, now=now)
        if run:
            runs.append(run)
    return runs


def scheduler_is_late(now=None):
    """True si algún proceso activo debería haberse lanzado hace rato (el lanzador no está en marcha)."""
    now = now or timezone.now()
    return ScheduledJob.objects.filter(
        enabled=True, running_since__isnull=True, next_run_at__lt=now - LATE_AFTER,
    ).exists()


def notify_failure(run):
    """Avisa por email al personal de Zyra de que un proceso ha fallado."""
    recipients = list(
        get_user_model().objects.filter(is_staff=True, is_active=True).exclude(email="").values_list("email", flat=True)
    )
    if not recipients:
        return False
    context = {"run": run, "job": run.job, "spec": run.job.spec}
    email = build_email(
        _("Zyra · Ha fallado el proceso %(job)s") % {"job": run.job.name},
        render_to_string("backoffice/emails/job_failed.txt", context),
        render_to_string("backoffice/emails/job_failed.html", context),
        to=recipients,
    )
    try:
        email.send(fail_silently=False)
    except Exception:
        logger.exception("No se pudo enviar el aviso del fallo del proceso %s", run.job.name)
        return False
    return True
