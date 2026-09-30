"""
Cifras del dashboard del back-office. Todas se calculan al vuelo sobre los datos
de todos los clubes; cuando haya muchos datos se guardará un resumen diario.
"""
import datetime

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import TruncWeek
from django.utils import timezone

from call.models import Call
from core.models import Club, Invitation, Membership
from match.models import Match
from players.models import Player

User = get_user_model()

# Un club está "activo" si ha jugado (o tiene programado) un partido en esta ventana.
ACTIVE_CLUB_DAYS = 30
# Un club lleva "sin actividad" si no tiene partidos en esta ventana.
AT_RISK_DAYS = 60


def _subquery_count(model, fk, **filters):
    qs = (
        model.objects.filter(**{fk: OuterRef("pk")}, **filters)
        .order_by().values(fk).annotate(n=Count("pk")).values("n")
    )
    return Subquery(qs)


def annotate_clubs(qs):
    """Añade a cada club sus contadores (miembros, jugadores, partidos) y la fecha del último partido."""
    today = timezone.localdate()
    last_match = (
        Match.objects.filter(club=OuterRef("pk"), start_date__lte=today)
        .order_by("-start_date").values("start_date")[:1]
    )
    return qs.annotate(
        n_members=_subquery_count(Membership, "club"),
        n_admins=_subquery_count(Membership, "club", role=Membership.ADMIN),
        n_players=_subquery_count(Player, "club", in_team=True),
        n_matches=_subquery_count(Match, "club"),
        last_match=Subquery(last_match),
    )


def google_user_ids():
    return SocialAccount.objects.filter(provider="google").values("user_id")


def dashboard_kpis():
    now = timezone.now()
    today = timezone.localdate()
    active_from = today - datetime.timedelta(days=ACTIVE_CLUB_DAYS)
    at_risk_from = today - datetime.timedelta(days=AT_RISK_DAYS)

    users = User.objects.all()
    clubs = Club.objects.all()
    active_clubs = clubs.filter(
        matches__start_date__gte=active_from, matches__start_date__lte=today + datetime.timedelta(days=ACTIVE_CLUB_DAYS),
    ).distinct()

    invitations = Invitation.objects.all()
    inv_used_30 = invitations.filter(used_at__gte=now - datetime.timedelta(days=30)).count()
    inv_created_30 = invitations.filter(created_at__gte=now - datetime.timedelta(days=30)).count()

    return {
        "clubs": {
            "total": clubs.count(),
            "new_30": clubs.filter(created_at__gte=now - datetime.timedelta(days=30)).count(),
            "active": active_clubs.count(),
        },
        "users": {
            "total": users.count(),
            "new_7": users.filter(date_joined__gte=now - datetime.timedelta(days=7)).count(),
            "new_30": users.filter(date_joined__gte=now - datetime.timedelta(days=30)).count(),
            "active_24h": users.filter(last_login__gte=now - datetime.timedelta(hours=24)).count(),
            "active_7": users.filter(last_login__gte=now - datetime.timedelta(days=7)).count(),
            "active_30": users.filter(last_login__gte=now - datetime.timedelta(days=30)).count(),
            "google": users.filter(pk__in=google_user_ids()).count(),
            "without_club": users.filter(memberships__isnull=True).count(),
        },
        "activity": {
            "players": Player.objects.filter(in_team=True).count(),
            "matches_30": Match.objects.filter(start_date__gte=active_from, start_date__lte=today).count(),
            "matches_upcoming": Match.objects.filter(start_date__gt=today, start_date__lte=today + datetime.timedelta(days=30)).count(),
            "calls_open": Call.objects.filter(draft_mode=True, match__start_date__gte=today).count(),
        },
        "invitations": {
            "pending": invitations.filter(used_at__isnull=True, expires_at__gt=now).count(),
            "created_30": inv_created_30,
            "used_30": inv_used_30,
            "conversion_30": round(100 * inv_used_30 / inv_created_30) if inv_created_30 else None,
        },
        "signups_by_week": signups_by_week(weeks=8),
        "recent_clubs": annotate_clubs(clubs.order_by("-created_at"))[:5],
        "recent_users": users.order_by("-date_joined")[:5],
        "inactive_clubs": annotate_clubs(
            clubs.filter(created_at__lt=now - datetime.timedelta(days=AT_RISK_DAYS))
            .exclude(matches__start_date__gte=at_risk_from)
        ).order_by("name")[:10],
    }


def signups_by_week(weeks=8):
    """Altas de usuarios por semana (lunes), las últimas `weeks` semanas, incluidas las de cero altas."""
    today = timezone.localdate()
    this_monday = today - datetime.timedelta(days=today.weekday())
    mondays = [this_monday - datetime.timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]
    start = timezone.make_aware(datetime.datetime.combine(mondays[0], datetime.time.min))

    rows = (
        User.objects.filter(date_joined__gte=start)
        .annotate(week=TruncWeek("date_joined")).values("week").annotate(n=Count("pk"))
    )
    counts = {}
    for row in rows:
        week = row["week"]
        week = week.date() if isinstance(week, datetime.datetime) else week
        counts[week] = counts.get(week, 0) + row["n"]

    peak = max(counts.values(), default=0) or 1
    return [
        {"week": monday, "n": counts.get(monday, 0), "pct": round(100 * counts.get(monday, 0) / peak)}
        for monday in mondays
    ]
