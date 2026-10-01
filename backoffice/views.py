import csv
import datetime
import re
from urllib.parse import urlencode

from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.models import Club, Invitation, Membership
from match.models import Match
from players.models import Player

from . import importer, sql
from .decorators import staff_required, superuser_required
from .metrics import (
    AT_RISK_DAYS, ONLINE_MINUTES, annotate_clubs, dashboard_kpis, google_user_ids, load_metrics, online_users,
)
from .middleware import SLOW_MS, flush_metrics
from .models import ImportJob, JobRun, QueryLog, SavedQuery, ScheduledJob
from .scheduler import SCHEDULER_TIME_ZONE, scheduler_is_late, start_manual_run, sync_jobs
from .templatetags.backoffice_tags import duration as duration_filter

User = get_user_model()

PAGE_SIZE = 25


def _page(request, qs):
    return Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))


def _extra(request, *keys):
    """Parámetros de filtro para mantenerlos en los enlaces de paginación."""
    params = {k: request.GET[k] for k in keys if request.GET.get(k)}
    return "&" + urlencode(params) if params else ""


@staff_required
def dashboard(request):
    flush_metrics()
    day_ago = timezone.now() - datetime.timedelta(hours=24)
    return render(request, "backoffice/dashboard.html", {
        "section": "dashboard", "kpis": dashboard_kpis(), "at_risk_days": AT_RISK_DAYS,
        "jobs_failed_24h": JobRun.objects.filter(status=JobRun.ERROR, started_at__gte=day_ago).count(),
        "scheduler_late": scheduler_is_late(),
    })


@staff_required
def load(request):
    flush_metrics()
    return render(request, "backoffice/load.html", {
        "section": "load", "online": online_users(), "online_minutes": ONLINE_MINUTES,
        "load": load_metrics(), "slow_ms": SLOW_MS,
    })


CLUB_ORDERINGS = {
    "recent": F("created_at").desc(),
    "name": F("name").asc(),
    "members": F("n_members").desc(nulls_last=True),
    "activity": F("last_match").desc(nulls_last=True),
}


@staff_required
def club_list(request):
    q = request.GET.get("q", "").strip()
    activity = request.GET.get("activity", "")
    order = request.GET.get("order", "recent")

    clubs = annotate_clubs(Club.objects.all())
    if q:
        clubs = clubs.filter(Q(name__icontains=q) | Q(slug__icontains=q))
    today = timezone.localdate()
    recent = today - datetime.timedelta(days=AT_RISK_DAYS)
    if activity == "active":
        clubs = clubs.filter(last_match__gte=recent)
    elif activity == "inactive":
        clubs = clubs.filter(Q(last_match__lt=recent) | Q(last_match__isnull=True))

    if order not in CLUB_ORDERINGS:
        order = "recent"
    clubs = clubs.order_by(CLUB_ORDERINGS[order], "name")

    return render(request, "backoffice/club_list.html", {
        "section": "clubs", "page": _page(request, clubs), "q": q, "activity": activity, "order": order,
        "extra": _extra(request, "q", "activity", "order"), "at_risk_days": AT_RISK_DAYS,
    })


@staff_required
def club_detail(request, club_id):
    club = get_object_or_404(annotate_clubs(Club.objects.all()), pk=club_id)
    today = timezone.localdate()
    matches = Match.objects.filter(club=club).select_related("local", "visiting")
    players = Player.objects.filter(club=club)

    return render(request, "backoffice/club_detail.html", {
        "section": "clubs",
        "club": club,
        "memberships": club.memberships.select_related("user").order_by("role", "user__username"),
        "players_total": players.count(),
        "players_active": players.filter(in_team=True).count(),
        "rivals": club.teams.filter(is_own=False).count(),
        "past_matches": matches.filter(start_date__lte=today).order_by("-start_date")[:10],
        "upcoming_matches": matches.filter(start_date__gt=today).order_by("start_date")[:5],
        "invitations": club.invitations.select_related("created_by", "used_by")[:10],
        "now": timezone.now(),
    })


@staff_required
def user_list(request):
    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")

    users = User.objects.annotate(n_clubs=Count("memberships")).order_by("-date_joined")
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )
    month_ago = timezone.now() - datetime.timedelta(days=30)
    if kind == "staff":
        users = users.filter(is_staff=True)
    elif kind == "google":
        users = users.filter(pk__in=google_user_ids())
    elif kind == "no_club":
        users = users.filter(n_clubs=0)
    elif kind == "inactive":
        users = users.filter(Q(last_login__lt=month_ago) | Q(last_login__isnull=True))

    page = _page(request, users)
    google_ids = set(
        SocialAccount.objects.filter(provider="google", user__in=[u.pk for u in page]).values_list("user_id", flat=True)
    )
    for u in page:
        u.uses_google = u.pk in google_ids

    return render(request, "backoffice/user_list.html", {
        "section": "users", "page": page, "q": q, "kind": kind, "extra": _extra(request, "q", "kind"),
    })


@staff_required
def user_detail(request, user_id):
    member = get_object_or_404(User, pk=user_id)
    providers = SocialAccount.objects.filter(user=member).values_list("provider", flat=True)
    login_methods = (["Contraseña"] if member.has_usable_password() else []) + [p.capitalize() for p in providers]
    return render(request, "backoffice/user_detail.html", {
        "section": "users",
        "member": member,
        "memberships": Membership.objects.filter(user=member).select_related("club").order_by("club__name"),
        "login_methods": login_methods,
        "invitation_used": Invitation.objects.filter(used_by=member).select_related("club", "created_by").first(),
        "invitations_sent": Invitation.objects.filter(created_by=member).count(),
    })


# ---------- Procesos programados ----------

def _last_runs(jobs):
    last = {}
    for run in JobRun.objects.filter(job__in=jobs).order_by("job_id", "-started_at").select_related("job"):
        last.setdefault(run.job_id, run)
    return last


def _back(request):
    """Vuelve a la página desde la que se pulsó el botón (solo rutas de este sitio)."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("backoffice:job_list")


@staff_required
def job_list(request):
    jobs = list(sync_jobs())
    last = _last_runs(jobs)
    day_ago = timezone.now() - datetime.timedelta(hours=24)
    for job in jobs:
        job.last_run = last.get(job.pk)
    return render(request, "backoffice/job_list.html", {
        "section": "jobs", "jobs": jobs, "late": scheduler_is_late(), "time_zone": SCHEDULER_TIME_ZONE,
        "failed_24h": JobRun.objects.filter(status=JobRun.ERROR, started_at__gte=day_ago).count(),
        "recent_runs": JobRun.objects.select_related("job")[:10],
    })


@staff_required
def job_detail(request, name):
    sync_jobs()
    job = get_object_or_404(ScheduledJob, name=name)
    runs = job.runs.select_related("triggered_by")
    return render(request, "backoffice/job_detail.html", {
        "section": "jobs", "job": job, "page": _page(request, runs), "time_zone": SCHEDULER_TIME_ZONE,
        "ok_count": runs.filter(status=JobRun.OK).count(), "error_count": runs.filter(status=JobRun.ERROR).count(),
    })


@staff_required
def run_list(request):
    status = request.GET.get("status", "")
    job_name = request.GET.get("job", "")
    runs = JobRun.objects.select_related("job", "triggered_by")
    if status in dict(JobRun.STATUSES):
        runs = runs.filter(status=status)
    if job_name:
        runs = runs.filter(job__name=job_name)
    return render(request, "backoffice/run_list.html", {
        "section": "jobs", "page": _page(request, runs), "status": status, "job_name": job_name,
        "statuses": JobRun.STATUSES, "jobs": sync_jobs(), "extra": _extra(request, "status", "job"),
    })


@staff_required
def run_detail(request, run_id):
    run = get_object_or_404(JobRun.objects.select_related("job", "triggered_by"), pk=run_id)
    return render(request, "backoffice/run_detail.html", {"section": "jobs", "run": run})


@staff_required
@require_POST
def job_toggle(request, name):
    job = get_object_or_404(ScheduledJob, name=name)
    job.enabled = not job.enabled
    job.save(update_fields=["enabled"])
    messages.success(request, f"{job.name}: {'activado' if job.enabled else 'en pausa'}.")
    return _back(request)


@staff_required
@require_POST
def job_run_now(request, name):
    job = get_object_or_404(ScheduledJob, name=name)
    args = []
    for param in job.spec.params if job.spec else ():
        value = request.POST.get(param.name, "").strip()
        if not re.fullmatch(param.pattern, value):
            messages.error(request, f"Indica un valor válido para «{param.label}».")
            return redirect("backoffice:job_detail", name=job.name)
        args.append(value)
    run = start_manual_run(job, request.user, args)
    if run is None:
        messages.error(request, f"{job.name} ya se está ejecutando.")
        return _back(request)
    return redirect("backoffice:run_detail", run_id=run.pk)


@staff_required
def run_live(request, run_id):
    """Salida de una ejecución a partir de `offset`, para la consola en directo."""
    run = get_object_or_404(JobRun, pk=run_id)
    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except ValueError:
        offset = 0
    output = run.output or ""
    return JsonResponse({
        "status": run.status,
        "status_label": run.get_status_display(),
        "finished": run.status != JobRun.RUNNING,
        "output": output[offset:],
        "offset": len(output),
        "error": run.error if run.status == JobRun.ERROR else "",
        "duration": duration_filter(run.duration) if run.finished_at else "",
    })


# ---------- Consola SQL ----------

def _csv_response(result, filename):
    """CSV que Excel abre bien en español: UTF-8 con BOM y separador punto y coma."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(result.columns)
    for row in result.rows:
        writer.writerow(["" if v is None else v for v in row])
    return response


def _export_name(saved):
    base = slugify(saved.name) if saved else "consulta"
    return f"zyra-{base}-{timezone.localtime():%Y%m%d-%H%M}.csv"


@superuser_required
def sql_console(request):
    saved = None
    if request.GET.get("saved"):
        saved = SavedQuery.objects.filter(pk=request.GET["saved"]).first()
    query = request.POST.get("sql") if request.method == "POST" else (saved.sql if saved else "")
    action = request.POST.get("action", "")
    result = error = None

    if request.method == "POST" and action in ("run", "export"):
        export = action == "export"
        log = QueryLog(user=request.user, sql=query or "", exported=export)
        try:
            result = sql.run(query, limit=sql.EXPORT_LIMIT if export else sql.DISPLAY_LIMIT)
            log.row_count, log.duration_ms = result.row_count, result.duration_ms
        except sql.QueryError as exc:
            error = log.error = str(exc)
        log.save()
        if export and result:
            return _csv_response(result, _export_name(saved))

    elif request.method == "POST" and action == "save":
        name = request.POST.get("name", "").strip()
        try:
            sql.validate(query)
        except sql.QueryError as exc:
            error = str(exc)
        else:
            if not name:
                error = "Ponle un nombre a la consulta para guardarla."
            else:
                saved, created = SavedQuery.objects.update_or_create(
                    name=name, defaults={"sql": sql.clean(query), "description": request.POST.get("description", "").strip()[:255],
                                         "created_by": request.user},
                )
                messages.success(request, f"Consulta «{saved.name}» {'guardada' if created else 'actualizada'}.")
                return redirect(f"{request.path}?saved={saved.pk}")

    return render(request, "backoffice/sql_console.html", {
        "section": "sql", "query": query or "", "result": result, "error": error, "saved": saved,
        "saved_queries": SavedQuery.objects.all(), "schema": sql.schema(),
        "history": QueryLog.objects.filter(user=request.user)[:15],
        "display_limit": sql.DISPLAY_LIMIT, "export_limit": sql.EXPORT_LIMIT, "timeout": sql.TIMEOUT_SECONDS,
    })


@superuser_required
@require_POST
def sql_delete_saved(request, query_id):
    saved = get_object_or_404(SavedQuery, pk=query_id)
    saved.delete()
    messages.success(request, f"Consulta «{saved.name}» borrada.")
    return redirect("backoffice:sql_console")


@superuser_required
def sql_log(request):
    return render(request, "backoffice/sql_log.html", {
        "section": "sql", "page": _page(request, QueryLog.objects.select_related("user")),
    })


# ---------- Importación de datos ----------

PREVIEW_ROWS = 100


@superuser_required
def import_list(request):
    if request.method == "POST":
        entity_key, mode = request.POST.get("entity"), request.POST.get("mode")
        club = Club.objects.filter(pk=request.POST.get("club")).first()
        upload = request.FILES.get("file")
        error = None
        if entity_key not in importer.ENTITIES or mode not in dict(importer.MODES) or club is None:
            error = "Elige qué importar, a qué club y cómo."
        elif upload is None:
            error = "Sube un fichero CSV."
        else:
            try:
                text = importer.decode(upload.read())
                headers, _ = importer.read_csv(text)
            except importer.ImportFileError as exc:
                error = str(exc)
        if error:
            messages.error(request, error)
            return redirect("backoffice:import_list")
        job = ImportJob.objects.create(
            user=request.user, club=club, entity=entity_key, mode=mode, filename=upload.name[:255], content=text,
            mapping=importer.guess_mapping(importer.ENTITIES[entity_key], headers),
        )
        return redirect("backoffice:import_map", job_id=job.pk)

    return render(request, "backoffice/import_list.html", {
        "section": "import", "entities": importer.ENTITIES.values(), "modes": importer.MODES,
        "clubs": Club.objects.order_by("name"), "page": _page(request, ImportJob.objects.select_related("club", "user")),
        "max_rows": importer.MAX_ROWS,
    })


def _draft(job_id):
    return get_object_or_404(ImportJob.objects.select_related("club"), pk=job_id, status=ImportJob.DRAFT)


@superuser_required
def import_map(request, job_id):
    job = _draft(job_id)
    entity = job.entity_spec
    headers, rows = importer.read_csv(job.content)
    if request.method == "POST":
        mapping = {}
        for f in entity.all_fields():
            value = request.POST.get(f"map_{f.name}", "")
            if value.isdigit() and int(value) < len(headers):
                mapping[f.name] = int(value)
        job.mapping = mapping
        job.save(update_fields=["mapping"])
        return redirect("backoffice:import_preview", job_id=job.pk)
    return render(request, "backoffice/import_map.html", {
        "section": "import", "job": job, "entity": entity, "headers": list(enumerate(headers)),
        "sample": rows[:3], "fields": [(f, job.mapping.get(f.name)) for f in entity.all_fields()],
    })


def _show(value):
    if isinstance(value, bool):
        return "sí" if value else "no"
    return value


def _validate(job):
    headers, rows = importer.read_csv(job.content)
    return importer.process(job.entity_spec, job.club, job.mode, headers, rows, job.mapping)


@superuser_required
def import_preview(request, job_id):
    job = _draft(job_id)
    try:
        results = _validate(job)
    except importer.ImportFileError as exc:
        messages.error(request, str(exc))
        return redirect("backoffice:import_map", job_id=job.pk)

    if request.GET.get("errors") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="errores-{slugify(job.filename)}.csv"'
        response.write("﻿")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(["Línea", "Errores"])
        for r in results:
            if not r.ok:
                writer.writerow([r.line, " | ".join(r.errors)])
        return response

    errors = [r for r in results if not r.ok]
    entity = job.entity_spec
    fields = [f for f in entity.all_fields() if f.name in job.mapping]
    return render(request, "backoffice/import_preview.html", {
        "section": "import", "job": job, "entity": entity, "fields": fields,
        "rows": [(r, [_show(r.values.get(f.name, "")) for f in fields]) for r in (errors or results)[:PREVIEW_ROWS]],
        "total": len(results), "errors": len(errors),
        "creates": sum(r.action == importer.CREATE for r in results if r.ok),
        "updates": sum(r.action == importer.UPDATE for r in results if r.ok),
        "preview_rows": PREVIEW_ROWS,
    })


@superuser_required
@require_POST
def import_confirm(request, job_id):
    job = _draft(job_id)
    try:
        results = importer.run_import(job)
    except importer.ImportFileError as exc:
        messages.error(request, str(exc))
        return redirect("backoffice:import_map", job_id=job.pk)
    if any(not r.ok for r in results):
        messages.error(request, "Hay filas con errores: no se ha importado nada.")
        return redirect("backoffice:import_preview", job_id=job.pk)
    job.status, job.finished_at = ImportJob.DONE, timezone.now()
    job.created_count = len(job.result["created"])
    job.updated_count = len(job.result["updated"])
    job.save()
    messages.success(request, f"Importación hecha: {job.created_count} creados y {job.updated_count} actualizados.")
    return redirect("backoffice:import_list")


@superuser_required
@require_POST
def import_undo(request, job_id):
    job = get_object_or_404(ImportJob, pk=job_id, status=ImportJob.DONE)
    deleted, restored = importer.undo_import(job)
    job.status, job.undone_at = ImportJob.UNDONE, timezone.now()
    job.save(update_fields=["status", "undone_at"])
    messages.success(request, f"Importación deshecha: {deleted} borrados y {restored} restaurados.")
    return redirect("backoffice:import_list")


@superuser_required
def import_template(request, entity):
    spec = importer.ENTITIES.get(entity)
    if spec is None:
        raise Http404
    response = HttpResponse(importer.template_csv(spec), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="plantilla-{entity}.csv"'
    return response
