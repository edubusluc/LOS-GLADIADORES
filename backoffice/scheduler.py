"""
Lanzador de procesos programados. `python manage.py run_scheduler` debe ejecutarse
cada minuto (cron, systemd timer o el programador del hosting); en cada pasada
lanza los procesos a los que les toca y los pedidos con "Ejecutar ahora".
"""
import datetime
import io
import logging
import traceback
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from core.emails import build_email

from .cron import Cron
from .jobs import JOBS, SCHEDULER_TIME_ZONE
from .models import JobRun, ScheduledJob

logger = logging.getLogger(__name__)

# Guardamos como mucho esto de la salida de cada ejecución.
MAX_OUTPUT = 20_000
# Si el lanzador no ha pasado en este tiempo, el back-office avisa de que no está en marcha.
LATE_AFTER = datetime.timedelta(minutes=10)


def next_run(spec, after):
    local = after.astimezone(ZoneInfo(SCHEDULER_TIME_ZONE))
    return Cron(spec.schedule).next_after(local).astimezone(datetime.timezone.utc)


def sync_jobs(now=None):
    """Crea la fila de estado de los procesos nuevos y calcula su próxima ejecución."""
    now = now or timezone.now()
    for spec in JOBS:
        job, created = ScheduledJob.objects.get_or_create(name=spec.name)
        if created or job.next_run_at is None:
            job.next_run_at = next_run(spec, now)
            job.save(update_fields=["next_run_at"])
    return ScheduledJob.objects.filter(name__in=[s.name for s in JOBS])


def _clip(text):
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n… (salida recortada, {len(text) - MAX_OUTPUT} caracteres más)"


def _release_stale_locks(now):
    """Da por interrumpidas las ejecuciones que llevan más de su tiempo máximo en marcha."""
    for job in ScheduledJob.objects.filter(running_since__isnull=False):
        spec = job.spec
        limit = datetime.timedelta(minutes=spec.timeout_minutes if spec else 60)
        if now - job.running_since < limit:
            continue
        job.runs.filter(status=JobRun.RUNNING).update(
            status=JobRun.ERROR, finished_at=now,
            error=f"Interrumpida: seguía en marcha después de {int(limit.total_seconds() // 60)} minutos.",
        )
        ScheduledJob.objects.filter(pk=job.pk).update(running_since=None)


def run_job(job, trigger=JobRun.SCHEDULE, user=None, now=None):
    """
    Ejecuta un proceso y guarda la ejecución. Devuelve el JobRun, o None si el proceso
    ya estaba en marcha (otra pasada del lanzador lo tiene cogido).
    """
    now = now or timezone.now()
    spec = job.spec
    # Coger el proceso de forma atómica: solo una pasada puede ponerle la marca.
    if not ScheduledJob.objects.filter(pk=job.pk, running_since__isnull=True).update(running_since=now):
        return None

    run = JobRun.objects.create(job=job, trigger=trigger, triggered_by=user, started_at=now)
    out = io.StringIO()
    try:
        if spec is None:
            raise RuntimeError(f"El proceso {job.name} ya no existe en backoffice/jobs.py.")
        call_command(spec.command, *spec.args, stdout=out, stderr=out)
        run.status = JobRun.OK
    except BaseException as exc:  # SystemExit/CommandError incluidos: nada debe tumbar el lanzador
        run.status = JobRun.ERROR
        run.error = _clip("".join(traceback.format_exception(exc)))
        if isinstance(exc, KeyboardInterrupt):
            raise
    finally:
        finished = timezone.now()
        run.output = _clip(out.getvalue())
        run.finished_at = finished
        run.save()
        changes = {"running_since": None, "last_run_at": now}
        if trigger == JobRun.SCHEDULE and spec:
            changes["next_run_at"] = next_run(spec, finished)
        if trigger == JobRun.MANUAL:
            changes["run_requested_at"] = None
            changes["run_requested_by"] = None
        ScheduledJob.objects.filter(pk=job.pk).update(**changes)

    if run.status == JobRun.ERROR:
        notify_failure(run)
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
        f"Zyra · Ha fallado el proceso {run.job.name}",
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
