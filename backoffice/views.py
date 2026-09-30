import datetime
from urllib.parse import urlencode

from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import Club, Invitation, Membership
from match.models import Match
from players.models import Player

from .decorators import staff_required
from .metrics import (
    AT_RISK_DAYS, ONLINE_MINUTES, annotate_clubs, dashboard_kpis, google_user_ids, load_metrics, online_users,
)
from .middleware import SLOW_MS, flush_metrics
from .models import JobRun, ScheduledJob
from .scheduler import SCHEDULER_TIME_ZONE, scheduler_is_late, sync_jobs

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
    job.run_requested_at = timezone.now()
    job.run_requested_by = request.user
    job.save(update_fields=["run_requested_at", "run_requested_by"])
    messages.success(request, f"{job.name} se ejecutará en la próxima pasada del lanzador (como mucho en un minuto).")
    return _back(request)
