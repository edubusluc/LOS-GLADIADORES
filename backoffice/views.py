import datetime
from urllib.parse import urlencode

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from core.models import Club, Invitation, Membership
from match.models import Match
from players.models import Player

from .decorators import staff_required
from .metrics import (
    AT_RISK_DAYS, ONLINE_MINUTES, annotate_clubs, dashboard_kpis, google_user_ids, load_metrics, online_users,
)
from .middleware import SLOW_MS, flush_metrics

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
    return render(request, "backoffice/dashboard.html", {
        "section": "dashboard", "kpis": dashboard_kpis(), "at_risk_days": AT_RISK_DAYS,
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
