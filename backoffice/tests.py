import datetime

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Invitation, Membership
from core.services import create_club
from match.models import Match
from players.models import Player
from team.models import Team

from .metrics import dashboard_kpis, load_metrics, online_users, signups_by_week
from .middleware import flush_metrics
from .models import JobRun, RequestMetric, ScheduledJob, UserActivity

User = get_user_model()

PAGES = [
    ("backoffice:dashboard", []),
    ("backoffice:club_list", []),
    ("backoffice:user_list", []),
    ("backoffice:load", []),
    ("backoffice:job_list", []),
    ("backoffice:run_list", []),
]


class BackofficeAccessTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user("member", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.member)

    def test_anonymous_is_sent_to_login(self):
        for name, args in PAGES:
            response = self.client.get(reverse(name, args=args))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name, args=args)}", fetch_redirect_response=False)

    def test_club_admin_without_staff_gets_404(self):
        self.client.login(username="member", password="pass-12345")
        for name, args in PAGES + [("backoffice:club_detail", [self.club.id]), ("backoffice:user_detail", [self.member.id])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404, name)

    def test_staff_sees_every_page(self):
        User.objects.create_user("staff", password="pass-12345", is_staff=True)
        self.client.login(username="staff", password="pass-12345")
        for name, args in PAGES + [("backoffice:club_detail", [self.club.id]), ("backoffice:user_detail", [self.member.id])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_menu_link_only_for_staff(self):
        self.client.login(username="member", password="pass-12345")
        self.assertNotContains(self.client.get(reverse("home")), reverse("backoffice:dashboard"))
        self.member.is_staff = True
        self.member.save()
        self.assertContains(self.client.get(reverse("home")), reverse("backoffice:dashboard"))

    def test_django_admin_is_superuser_only(self):
        User.objects.create_user("staff", password="pass-12345", is_staff=True)
        self.client.login(username="staff", password="pass-12345")
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        User.objects.create_superuser("root", password="pass-12345")
        self.client.login(username="root", password="pass-12345")
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)


class BackofficeDataTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("staff", password="pass-12345", is_staff=True)
        self.admin_a = User.objects.create_user("ana", email="ana@example.com", password="pass-12345")
        self.admin_b = User.objects.create_user("bea", password="pass-12345")
        self.club_a = create_club("Club Alfa", "Sevilla", self.admin_a)
        self.club_b = create_club("Club Beta", "Madrid", self.admin_b)
        Player.objects.create(club=self.club_a, name="Pepe", last_name="Uno")
        Player.objects.create(club=self.club_a, name="Luis", last_name="Dos", in_team=False)
        rival = Team.objects.create(club=self.club_a, name="Rival", location="X")
        today = timezone.localdate()
        Match.objects.create(club=self.club_a, local=self.club_a.own_team, visiting=rival, start_date=today - datetime.timedelta(days=3))
        Match.objects.create(club=self.club_a, local=self.club_a.own_team, visiting=rival, start_date=today + datetime.timedelta(days=5))
        SocialAccount.objects.create(user=self.admin_b, provider="google", uid="123")
        self.client.login(username="staff", password="pass-12345")

    def test_dashboard_counts_across_all_clubs(self):
        kpis = dashboard_kpis()
        self.assertEqual(kpis["clubs"]["total"], 2)
        self.assertEqual(kpis["clubs"]["active"], 1)
        self.assertEqual(kpis["users"]["total"], 3)
        self.assertEqual(kpis["users"]["google"], 1)
        self.assertEqual(kpis["users"]["without_club"], 1)
        self.assertEqual(kpis["activity"]["players"], 1)
        self.assertEqual(kpis["activity"]["matches_30"], 1)
        self.assertEqual(kpis["activity"]["matches_upcoming"], 1)

    def test_invitation_conversion(self):
        Invitation.objects.create(club=self.club_a, created_by=self.admin_a)
        Invitation.objects.create(club=self.club_a, created_by=self.admin_a, used_by=self.admin_b, used_at=timezone.now())
        inv = dashboard_kpis()["invitations"]
        self.assertEqual((inv["created_30"], inv["used_30"], inv["conversion_30"], inv["pending"]), (2, 1, 50, 1))

    def test_signups_by_week_has_every_week(self):
        weeks = signups_by_week(weeks=8)
        self.assertEqual(len(weeks), 8)
        self.assertEqual(weeks[-1]["n"], 3)
        self.assertEqual(weeks[-1]["pct"], 100)

    def test_club_list_search_filters_and_counts(self):
        page = self.client.get(reverse("backoffice:club_list"), {"q": "alfa"}).context["page"]
        [club] = page.object_list
        self.assertEqual((club.name, club.n_members, club.n_players, club.n_matches), ("Club Alfa", 1, 1, 2))
        self.assertEqual(club.last_match, timezone.localdate() - datetime.timedelta(days=3))

        inactive = self.client.get(reverse("backoffice:club_list"), {"activity": "inactive"}).context["page"]
        self.assertEqual([c.name for c in inactive], ["Club Beta"])

    def test_club_list_orderings(self):
        for order in ["recent", "name", "members", "activity", "bogus"]:
            response = self.client.get(reverse("backoffice:club_list"), {"order": order})
            self.assertEqual(len(response.context["page"].object_list), 2, order)

    def test_user_list_filters(self):
        url = reverse("backoffice:user_list")
        names = lambda **p: [u.username for u in self.client.get(url, p).context["page"]]
        self.assertEqual(names(q="ana@"), ["ana"])
        self.assertEqual(names(kind="google"), ["bea"])
        self.assertEqual(names(kind="no_club"), ["staff"])
        self.assertEqual(names(kind="staff"), ["staff"])

    def test_detail_pages_show_club_data(self):
        response = self.client.get(reverse("backoffice:club_detail", args=[self.club_a.id]))
        self.assertContains(response, "ana@example.com")
        self.assertEqual(response.context["players_total"], 2)
        self.assertEqual(response.context["players_active"], 1)

        response = self.client.get(reverse("backoffice:user_detail", args=[self.admin_b.id]))
        self.assertContains(response, "Club Beta")
        self.assertContains(response, "Google")
        self.assertFalse(Membership.objects.filter(user=self.staff).exists())


class ActivityAndLoadTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        flush_metrics()
        RequestMetric.objects.all().delete()
        self.staff = User.objects.create_user("staff", password="pass-12345", is_staff=True)
        self.member = User.objects.create_user("member", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.member)

    def test_requests_mark_user_online_with_club_and_path(self):
        self.client.login(username="member", password="pass-12345")
        self.client.get(reverse("list_players"))
        activity = UserActivity.objects.get(user=self.member)
        self.assertEqual(activity.club, self.club)
        self.assertEqual(activity.last_path, reverse("list_players"))
        self.assertEqual([a.user for a in online_users()], [self.member])

    def test_activity_is_written_at_most_once_a_minute(self):
        self.client.login(username="member", password="pass-12345")
        self.client.get(reverse("home"))
        self.client.get(reverse("list_players"))
        self.assertEqual(UserActivity.objects.get(user=self.member).last_path, reverse("home"))

    def test_old_activity_is_not_online(self):
        UserActivity.objects.create(user=self.member, last_seen=timezone.now() - datetime.timedelta(minutes=10))
        self.assertEqual(online_users().count(), 0)

    def test_logout_removes_user_from_online(self):
        self.client.login(username="member", password="pass-12345")
        self.client.get(reverse("home"))
        self.client.post(reverse("logout"))
        self.assertFalse(UserActivity.objects.filter(user=self.member).exists())

    def test_requests_are_counted_per_minute(self):
        self.client.get(reverse("login"))
        self.client.get(reverse("login"))
        self.client.get("/static/style.css")  # los estáticos no cuentan
        flush_metrics()
        metric = RequestMetric.objects.get()
        self.assertEqual(metric.requests, 2)
        self.assertEqual(metric.errors, 0)

        self.client.get(reverse("login"))
        flush_metrics()
        self.assertEqual(RequestMetric.objects.get().requests, 3)

    def test_load_page_and_series(self):
        now = timezone.now().replace(second=0, microsecond=0)
        RequestMetric.objects.create(minute=now - datetime.timedelta(minutes=2), requests=10, errors=1, total_ms=1000, max_ms=400)
        RequestMetric.objects.create(minute=now - datetime.timedelta(hours=3), requests=5, total_ms=500, max_ms=100)
        data = load_metrics()
        self.assertEqual(len(data["minutes"]), 60)
        self.assertEqual(len(data["hours"]), 24)
        self.assertEqual(data["last_hour"]["requests"], 10)
        self.assertEqual(data["last_hour"]["avg_ms"], 100)
        self.assertEqual(data["last_hour"]["errors"], 1)
        self.assertEqual(data["last_day"]["requests"], 15)
        self.assertEqual(data["peak_minute"]["requests"], 10)
        self.assertEqual(sum(h["requests"] for h in data["hours"]), 15)

        self.client.login(username="staff", password="pass-12345")
        response = self.client.get(reverse("backoffice:load"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff")  # el propio staff aparece conectado

    def test_purge_command(self):
        from django.core.management import call_command
        RequestMetric.objects.create(minute=timezone.now() - datetime.timedelta(days=40), requests=1)
        RequestMetric.objects.create(minute=timezone.now().replace(second=0, microsecond=0), requests=1)
        call_command("purge_request_metrics", stdout=open("/dev/null", "w"))
        self.assertEqual(RequestMetric.objects.count(), 1)


class AgoFilterTests(TestCase):
    def test_ago(self):
        from .templatetags.backoffice_tags import ago
        now = timezone.now()
        self.assertEqual(ago(None), "nunca")
        self.assertEqual(ago(now), "ahora mismo")
        self.assertTrue(ago(now - datetime.timedelta(minutes=5)).startswith("hace 5"))
        self.assertEqual(ago(timezone.localdate()), "hoy")
        self.assertTrue(ago(timezone.localdate() - datetime.timedelta(days=3)).startswith("hace 3"))


class CronTests(TestCase):
    def at(self, *args):
        from zoneinfo import ZoneInfo
        return datetime.datetime(*args, tzinfo=ZoneInfo("Europe/Madrid"))

    def test_next_after(self):
        from .cron import Cron
        self.assertEqual(Cron("0 3 * * *").next_after(self.at(2026, 9, 30, 2, 59)), self.at(2026, 9, 30, 3, 0))
        self.assertEqual(Cron("0 3 * * *").next_after(self.at(2026, 9, 30, 3, 0)), self.at(2026, 10, 1, 3, 0))
        self.assertEqual(Cron("*/15 * * * *").next_after(self.at(2026, 9, 30, 10, 7)), self.at(2026, 9, 30, 10, 15))
        # Lunes (1) a las 8:30; el 30/9/2026 es miércoles.
        self.assertEqual(Cron("30 8 * * 1").next_after(self.at(2026, 9, 30, 12, 0)), self.at(2026, 10, 5, 8, 30))
        self.assertEqual(Cron("0 0 1 * *").next_after(self.at(2026, 9, 30, 12, 0)), self.at(2026, 10, 1, 0, 0))
        self.assertEqual(Cron("0 9 * * 0,6").next_after(self.at(2026, 9, 30, 12, 0)), self.at(2026, 10, 3, 9, 0))

    def test_invalid_expressions(self):
        from .cron import Cron, CronError
        for bad in ["", "* * * *", "61 * * * *", "a * * * *", "*/0 * * * *", "0 3 31 2 *"]:
            with self.assertRaises(CronError, msg=bad):
                Cron(bad).next_after(self.at(2026, 1, 1, 0, 0))

    def test_describe(self):
        from .cron import Cron
        self.assertEqual(Cron("0 3 * * *").describe(), "Cada día a las 03:00")
        self.assertEqual(Cron("*/5 * * * *").describe(), "Cada 5 minutos")
        self.assertEqual(Cron("30 8 * * 1").describe(), "Cada lunes a las 08:30")

    def test_registered_jobs_are_valid(self):
        from django.core.management import get_commands
        from .cron import Cron
        from .jobs import JOBS
        self.assertEqual(len({j.name for j in JOBS}), len(JOBS))
        for spec in JOBS:
            Cron(spec.schedule)
            self.assertIn(spec.command, get_commands(), spec.name)


class SchedulerTests(TestCase):
    def setUp(self):
        from unittest import mock
        from .jobs import JobSpec
        self.specs = [
            JobSpec(name="ok_job", description="Va bien", command="purge_request_metrics", schedule="0 3 * * *"),
            JobSpec(name="bad_job", description="Falla", command="no_existe", schedule="0 4 * * *"),
        ]
        patcher = mock.patch("backoffice.scheduler.JOBS", self.specs)
        patcher.start()
        self.addCleanup(patcher.stop)
        spec_patch = mock.patch("backoffice.jobs.JOBS", self.specs)
        spec_patch.start()
        self.addCleanup(spec_patch.stop)
        self.staff = User.objects.create_user("staff", email="staff@example.com", password="pass-12345", is_staff=True)

    def test_sync_creates_jobs_with_next_run(self):
        from .scheduler import sync_jobs
        jobs = {j.name: j for j in sync_jobs()}
        self.assertEqual(set(jobs), {"ok_job", "bad_job"})
        self.assertTrue(all(j.next_run_at > timezone.now() for j in jobs.values()))

    def test_due_jobs_run_and_are_logged(self):
        from django.core import mail
        from .scheduler import run_due_jobs, sync_jobs
        sync_jobs()
        ScheduledJob.objects.update(next_run_at=timezone.now() - datetime.timedelta(minutes=1))
        runs = {r.job.name: r for r in run_due_jobs()}

        self.assertEqual(runs["ok_job"].status, JobRun.OK)
        self.assertIn("Borradas", runs["ok_job"].output)
        self.assertEqual(runs["bad_job"].status, JobRun.ERROR)
        self.assertIn("no_existe", runs["bad_job"].error)

        # Se reprograman para su siguiente hora y se libera la marca de "en curso".
        for job in ScheduledJob.objects.all():
            self.assertIsNone(job.running_since)
            self.assertGreater(job.next_run_at, timezone.now())
        # Aviso por email del fallo al personal de Zyra.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("bad_job", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["staff@example.com"])

        self.assertEqual(run_due_jobs(), [])  # nada más que hacer

    def test_paused_job_does_not_run_but_manual_request_does(self):
        from .scheduler import run_due_jobs, sync_jobs
        sync_jobs()
        ScheduledJob.objects.update(next_run_at=timezone.now() - datetime.timedelta(minutes=1), enabled=False)
        self.assertEqual(run_due_jobs(), [])

        ScheduledJob.objects.filter(name="ok_job").update(run_requested_at=timezone.now(), run_requested_by=self.staff)
        [run] = run_due_jobs()
        self.assertEqual((run.job.name, run.trigger, run.triggered_by), ("ok_job", JobRun.MANUAL, self.staff))
        self.assertIsNone(ScheduledJob.objects.get(name="ok_job").run_requested_at)

    def test_running_job_is_not_started_twice_and_stale_lock_is_released(self):
        from .scheduler import run_due_jobs, run_job, sync_jobs
        sync_jobs()
        job = ScheduledJob.objects.get(name="ok_job")
        ScheduledJob.objects.filter(pk=job.pk).update(running_since=timezone.now())
        self.assertIsNone(run_job(job))

        long_ago = timezone.now() - datetime.timedelta(hours=2)
        stuck = JobRun.objects.create(job=job, started_at=long_ago)
        ScheduledJob.objects.filter(pk=job.pk).update(running_since=long_ago, next_run_at=timezone.now())
        runs = run_due_jobs()
        stuck.refresh_from_db()
        self.assertEqual(stuck.status, JobRun.ERROR)
        self.assertIn("Interrumpida", stuck.error)
        self.assertEqual([r.status for r in runs], [JobRun.OK])

    def test_scheduler_is_late(self):
        from .scheduler import scheduler_is_late, sync_jobs
        sync_jobs()
        self.assertFalse(scheduler_is_late())
        ScheduledJob.objects.filter(name="ok_job").update(next_run_at=timezone.now() - datetime.timedelta(minutes=30))
        self.assertTrue(scheduler_is_late())

    def test_pages_and_actions(self):
        from .scheduler import run_due_jobs, sync_jobs
        sync_jobs()
        self.client.login(username="staff", password="pass-12345")
        self.assertContains(self.client.get(reverse("backoffice:job_list")), "ok_job")

        response = self.client.post(reverse("backoffice:job_run_now", args=["ok_job"]))
        self.assertRedirects(response, reverse("backoffice:job_list"))
        self.assertIsNotNone(ScheduledJob.objects.get(name="ok_job").run_requested_at)
        [run] = run_due_jobs()

        detail = reverse("backoffice:job_detail", args=["ok_job"])
        self.client.post(reverse("backoffice:job_toggle", args=["ok_job"]), {"next": detail})
        self.assertFalse(ScheduledJob.objects.get(name="ok_job").enabled)
        # "next" solo acepta rutas de este sitio.
        response = self.client.post(reverse("backoffice:job_toggle", args=["ok_job"]), {"next": "https://evil.example/"})
        self.assertRedirects(response, reverse("backoffice:job_list"))

        self.assertContains(self.client.get(detail), "Correcta")
        self.assertContains(self.client.get(reverse("backoffice:run_detail", args=[run.id])), "Borradas")
        log = self.client.get(reverse("backoffice:run_list"), {"status": "ok", "job": "ok_job"})
        self.assertEqual([r.id for r in log.context["page"]], [run.id])

    def test_actions_need_post_and_staff(self):
        self.client.login(username="staff", password="pass-12345")
        self.assertEqual(self.client.get(reverse("backoffice:job_run_now", args=["ok_job"])).status_code, 405)
        User.objects.create_user("member", password="pass-12345")
        self.client.login(username="member", password="pass-12345")
        self.assertEqual(self.client.post(reverse("backoffice:job_run_now", args=["ok_job"])).status_code, 404)

    def test_purge_job_runs(self):
        from django.core.management import call_command
        from .scheduler import sync_jobs
        sync_jobs()
        job = ScheduledJob.objects.first()
        JobRun.objects.create(job=job, status=JobRun.OK, started_at=timezone.now() - datetime.timedelta(days=100))
        JobRun.objects.create(job=job, status=JobRun.OK, started_at=timezone.now())
        call_command("purge_job_runs", stdout=open("/dev/null", "w"))
        self.assertEqual(JobRun.objects.count(), 1)
