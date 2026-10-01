from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Membership
from core.services import create_club
from team.models import Team

from .models import Player, SnpAccount
from .scraper import SnpScrapeError, parse_score, parse_team_id
from .snp import match_scores, normalize, sync_club

User = get_user_model()

GALAXY_URL = (
    "https://snpgalaxy.com/main/i/abc___def/i_:ghi+jkl/"
    "u_:aHR0cHM6Ly9zZXJpZXNuYWNpb25hbGVzZGVwYWRlbC5zbnBnYWxheHkuY29tL2VxdWlwby92aWV3LzQzODA="
)
DIRECT_URL = "https://seriesnacionalesdepadel.snpgalaxy.com/equipo/view/4380"


class ScraperHelpersTests(TestCase):
    def test_parse_team_id(self):
        self.assertEqual(parse_team_id(" 4380 "), "4380")
        self.assertEqual(parse_team_id(DIRECT_URL), "4380")
        self.assertEqual(parse_team_id(GALAXY_URL), "4380")
        self.assertIsNone(parse_team_id("https://snpgalaxy.com/main"))

    def test_parse_score(self):
        self.assertEqual(parse_score("1.234,5"), 1234.5)
        self.assertEqual(parse_score("12,5 / 3"), 12.5)
        self.assertEqual(parse_score(""), 0.0)
        self.assertEqual(parse_score("n/d"), 0.0)


class MatchScoresTests(TestCase):
    def setUp(self):
        self.club = create_club("Club A", "Sevilla", User.objects.create_user("admin", password="x"))

    def player(self, name, last_name):
        return Player.objects.create(club=self.club, name=name, last_name=last_name)

    def test_normalize_ignores_case_accents_and_punctuation(self):
        self.assertEqual(normalize("  JOSÉ  Pérez-Ruíz "), "jose perez ruiz")
        self.assertEqual(normalize("Íñigo"), "inigo")

    def test_matches_ignoring_case_accents_category_and_second_surname(self):
        jose = self.player("Jose", "perez")
        maria = self.player("María José", "Gómez Ruiz")
        matched, unmatched, ambiguous = match_scores([jose, maria], [
            {"name": "JOSÉ PÉREZ LÓPEZ 500", "score": 10.0},
            {"name": "Maria Jose Gomez Ruiz Future", "score": 20.0},
            {"name": "Otro Jugador 500", "score": 5.0},
        ])
        self.assertEqual({(p.pk, s) for p, s, _ in matched}, {(jose.pk, 10.0), (maria.pk, 20.0)})
        self.assertEqual(unmatched, ["Otro Jugador 500"])
        self.assertEqual(ambiguous, [])

    def test_exact_match_wins_over_prefix(self):
        short = self.player("Juan", "García")
        full = self.player("Juan", "García López")
        matched, _, ambiguous = match_scores([short, full], [{"name": "Juan García López", "score": 7.0}])
        self.assertEqual([(p.pk, s) for p, s, _ in matched], [(full.pk, 7.0)])
        self.assertEqual(ambiguous, [])

    def test_ambiguous_names_are_not_assigned(self):
        a = self.player("Juan", "García López")
        b = self.player("Juan", "García Ruiz")
        matched, _, ambiguous = match_scores([a, b], [{"name": "Juan García", "score": 7.0}])
        self.assertEqual(matched, [])
        self.assertEqual(ambiguous, ["Juan García"])


@override_settings(FIELD_ENCRYPTION_KEY="")
class SnpAccountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.admin)
        self.player = Player.objects.create(club=self.club, name="Ana", last_name="Álvarez")

    def make_account(self, club=None):
        account = SnpAccount(club=club or self.club, team_id="4380")
        account.username = "capitan"
        account.password = "secreto"
        account.save()
        return account

    def test_credentials_are_stored_encrypted(self):
        account = self.make_account()
        raw = SnpAccount.objects.values("username_encrypted", "password_encrypted").get(pk=account.pk)
        self.assertNotIn("capitan", raw["username_encrypted"])
        self.assertNotIn("secreto", raw["password_encrypted"])
        account.refresh_from_db()
        self.assertEqual((account.username, account.password), ("capitan", "secreto"))

    def test_sync_updates_scores_and_records_result(self):
        account = self.make_account()
        scraper = mock.Mock(return_value=[{"name": "ANA ALVAREZ 500", "score": 42.5}])
        result = sync_club(account, scraper=scraper)
        scraper.assert_called_once_with("capitan", "secreto", "4380")
        self.assertTrue(result.ok)
        self.player.refresh_from_db()
        self.assertEqual(self.player.snp_score, 42.5)
        account.refresh_from_db()
        self.assertTrue(account.last_sync_ok)
        self.assertIsNotNone(account.last_sync_at)

    def test_sync_failure_is_recorded_without_touching_scores(self):
        account = self.make_account()
        result = sync_club(account, scraper=mock.Mock(side_effect=SnpScrapeError("SNP no ha aceptado el usuario")))
        self.assertFalse(result.ok)
        account.refresh_from_db()
        self.assertFalse(account.last_sync_ok)
        self.assertIn("no ha aceptado", account.last_sync_message)
        self.player.refresh_from_db()
        self.assertIsNone(self.player.snp_score)

    def test_command_runs_club_by_club(self):
        self.make_account()
        other_admin = User.objects.create_user("other", password="x")
        other_club = create_club("Club B", "Madrid", other_admin)
        Player.objects.create(club=other_club, name="Bea", last_name="Beta")
        self.make_account(other_club)
        create_club("Club sin cuenta", "Cádiz", User.objects.create_user("third", password="x"))

        calls = []

        def fake_scrape(username, password, team_id, **options):
            calls.append(username)
            return [{"name": "Ana Alvarez", "score": 1.0}, {"name": "Bea Beta", "score": 2.0}]

        out = StringIO()
        with mock.patch("players.snp.scrape_scores", fake_scrape):
            call_command("update_snp_scores", stdout=out)
        self.assertEqual(len(calls), 2)
        self.assertEqual(Player.objects.get(name="Ana").snp_score, 1.0)
        self.assertEqual(Player.objects.get(name="Bea").snp_score, 2.0)
        output = out.getvalue()
        self.assertIn("Equipos a actualizar: 2\n", output)
        self.assertIn("Equipo que se actualiza: Club A\n", output)
        self.assertIn("Equipo que se actualiza: Club B\n", output)
        self.assertIn("Jugadores a actualizar: 1\n", output)
        self.assertIn("Jugadores actualizados correctamente: 1\n", output)
        self.assertIn("Jugadores no actualizados: 0\n", output)

        calls.clear()
        with mock.patch("players.snp.scrape_scores", fake_scrape):
            call_command("update_snp_scores", "--club", "club b", stdout=StringIO())
        self.assertEqual(len(calls), 1)

    def test_admin_can_save_account_and_password_is_kept_when_blank(self):
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(reverse("snp_account"), {
            "username": "capitan", "password": "secreto", "team": GALAXY_URL,
        })
        self.assertRedirects(response, reverse("snp_account"))
        page = self.client.get(reverse("snp_account")).content.decode()
        self.assertNotIn("secreto", page)
        self.assertIn("4380", page)

        self.client.post(reverse("snp_account"), {"username": "capitan2", "password": "", "team": ""})
        account = SnpAccount.objects.get(club=self.club)
        self.assertEqual((account.username, account.password, account.team_id), ("capitan2", "secreto", ""))

    def test_rejects_url_without_team(self):
        self.client.login(username="admin", password="pass-12345")
        response = self.client.post(reverse("snp_account"), {
            "username": "capitan", "password": "secreto", "team": "https://snpgalaxy.com/main",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SnpAccount.objects.exists())

    def test_members_cannot_see_account(self):
        viewer = User.objects.create_user("viewer", password="pass-12345")
        Membership.objects.create(user=viewer, club=self.club, role=Membership.MEMBER)
        self.make_account()
        self.client.login(username="viewer", password="pass-12345")
        self.assertEqual(self.client.get(reverse("snp_account")).status_code, 302)
        self.assertEqual(self.client.post(reverse("snp_account_delete")).status_code, 302)
        self.assertTrue(SnpAccount.objects.exists())

    def test_log_lists_players_not_updated(self):
        self.make_account()
        Player.objects.create(club=self.club, name="Luis", last_name="Gómez")
        out = StringIO()
        with mock.patch("players.snp.scrape_scores", lambda *a, **k: [{"name": "Ana Alvarez", "score": 3.0}]):
            call_command("update_snp_scores", stdout=out)
        self.assertIn("Jugadores a actualizar: 2\n", out.getvalue())
        self.assertIn("Jugadores actualizados correctamente: 1\n", out.getvalue())
        self.assertIn("Jugadores no actualizados: 1 (Luis Gómez)\n", out.getvalue())

        out = StringIO()
        with mock.patch("players.snp.scrape_scores", lambda *a, **k: [{"name": "Ana Alvarez", "score": 3.0},
                                                                     {"name": "Luis Gomes 500", "score": 4.0}]):
            call_command("update_snp_scores", stdout=out)
        self.assertIn("Nombres de SNP sin jugador en Zyra: Luis Gomes 500\n", out.getvalue())

    def test_sync_keeps_one_history_point_per_player_and_day(self):
        from .models import SnpScoreHistory, current_season
        account = self.make_account()
        sync_club(account, scraper=lambda *a, **k: [{"name": "Ana Alvarez", "score": 10.0}])
        sync_club(account, scraper=lambda *a, **k: [{"name": "Ana Alvarez", "score": 12.0}])
        history = SnpScoreHistory.objects.get(player=self.player)
        self.assertEqual((history.score, history.season), (12.0, current_season()))

    def test_player_statistics_include_snp_chart(self):
        import datetime
        from .models import SnpScoreHistory, current_season
        SnpScoreHistory.objects.create(player=self.player, date=datetime.date(2026, 9, 28), score=100.0, season=current_season())
        SnpScoreHistory.objects.create(player=self.player, date=datetime.date(2026, 10, 5), score=120.5, season=current_season())
        SnpScoreHistory.objects.create(player=self.player, date=datetime.date(2020, 1, 1), score=1.0, season="2019-2020")
        self.client.login(username="admin", password="pass-12345")
        response = self.client.get(reverse("player_statistics"), {"player": self.player.public_id})
        self.assertEqual(response.context["chart_snp"], {"labels": ["28/09", "05/10"], "scores": [100.0, 120.5]})
        self.assertContains(response, 'id="chartSnp"')

    def test_home_shows_snp_notice_to_admin_until_account_exists(self):
        viewer = User.objects.create_user("viewer", password="pass-12345")
        Membership.objects.create(user=viewer, club=self.club, role=Membership.MEMBER)
        self.client.login(username="admin", password="pass-12345")
        self.assertContains(self.client.get(reverse("home")), "Registra tu cuenta de SNP")
        self.client.login(username="viewer", password="pass-12345")
        self.assertNotContains(self.client.get(reverse("home")), "Registra tu cuenta de SNP")
        self.make_account()
        self.client.login(username="admin", password="pass-12345")
        self.assertNotContains(self.client.get(reverse("home")), "Registra tu cuenta de SNP")

    def test_snp_job_runs_weekly_on_monday_night(self):
        from backoffice.jobs import get_spec
        self.assertEqual(get_spec("update_snp_scores").schedule, "0 23 * * 1")


SNP_TEAM = [
    {"name": "ANA ALVAREZ 500", "score": 42.5},
    {"name": "PEDRO RAPOSO BELLERIN 1000", "score": 120.0},
    {"name": "MARIA JOSE GOMEZ RUIZ Future", "score": 33.0},
]


class SplitSnpNameTests(TestCase):
    def test_split(self):
        self.assertEqual(__import__("players.snp_import", fromlist=["x"]).split_snp_name("LUIS PEREZ GOMEZ GRAND SLAM"),
                         ("Luis", "Perez Gomez"))
        from .snp_import import split_snp_name
        self.assertEqual(split_snp_name("PEDRO RAPOSO BELLERIN 500"), ("Pedro", "Raposo Bellerin"))
        self.assertEqual(split_snp_name("MARIA JOSE GOMEZ RUIZ Future"), ("Maria Jose", "Gomez Ruiz"))
        self.assertEqual(split_snp_name("JUAN DE LA FUENTE LÓPEZ"), ("Juan", "de la Fuente López"))
        self.assertEqual(split_snp_name("ANA ALVAREZ"), ("Ana", "Alvarez"))
        self.assertEqual(split_snp_name("PELÉ"), ("Pelé", ""))


@override_settings(FIELD_ENCRYPTION_KEY="", SNP_IMPORT_INLINE=True)
class CompleteTeamTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.admin)
        account = SnpAccount(club=self.club)
        account.username, account.password = "capitan", "secreto"
        account.save()
        # Jugador existente con datos propios: no se debe tocar.
        self.ana = Player.objects.create(club=self.club, name="Ana", last_name="Álvarez", position="Revés", snp_score=1.0)
        self.client.login(username="admin", password="pass-12345")
        patcher = mock.patch("players.snp_import.scrape_scores", lambda *a, **k: SNP_TEAM)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_preview_then_confirm_creates_only_new_players(self):
        from .models import SnpScoreHistory, SnpTeamImport
        self.assertContains(self.client.get(reverse("list_players")), "Completar equipo")
        self.assertRedirects(self.client.post(reverse("complete_team_start")), reverse("list_players"))
        team_import = SnpTeamImport.objects.get()
        self.assertEqual(team_import.status, SnpTeamImport.READY)
        self.assertEqual([(p["name"], p["last_name"]) for p in team_import.to_add],
                         [("Maria Jose", "Gomez Ruiz"), ("Pedro", "Raposo Bellerin")])
        self.assertEqual(team_import.existing, [{"snp_name": "ANA ALVAREZ", "category": "500", "player": "Ana Álvarez"}])
        self.assertEqual(Player.objects.count(), 1)  # la búsqueda no crea nada

        page = self.client.get(reverse("list_players"))
        self.assertContains(page, 'id="completeTeamModal"')
        self.assertContains(page, "Pedro Raposo Bellerin")
        self.assertContains(page, "ya están registrados")
        self.assertEqual(self.client.get(reverse("complete_team_status", args=[team_import.public_id])).json()["status"], "ready")

        self.client.post(reverse("complete_team_confirm", args=[team_import.public_id]))
        pedro = Player.objects.get(name="Pedro")
        self.assertEqual((pedro.last_name, pedro.snp_score, pedro.in_team, pedro.team), ("Raposo Bellerin", 120.0, True, self.club.own_team))
        self.assertTrue(SnpScoreHistory.objects.filter(player=pedro, score=120.0).exists())
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.last_name, self.ana.position, self.ana.snp_score), ("Álvarez", "Revés", 1.0))
        self.assertEqual(Player.objects.count(), 3)

        # Solo una vez al mes.
        page = self.client.get(reverse("list_players"))
        self.assertContains(page, "Ya se ha completado este mes")
        self.client.post(reverse("complete_team_start"))
        self.assertEqual(SnpTeamImport.objects.count(), 1)

    def test_confirm_skips_players_created_in_the_meantime(self):
        from .models import SnpTeamImport
        self.client.post(reverse("complete_team_start"))
        team_import = SnpTeamImport.objects.get()
        Player.objects.create(club=self.club, name="Pedro", last_name="Raposo")
        self.client.post(reverse("complete_team_confirm", args=[team_import.public_id]))
        self.assertEqual(Player.objects.filter(name="Pedro").count(), 1)
        self.assertTrue(Player.objects.filter(name="Maria Jose").exists())

    def test_cancel_does_not_count_for_the_monthly_limit(self):
        from .models import SnpTeamImport
        self.client.post(reverse("complete_team_start"))
        team_import = SnpTeamImport.objects.get()
        self.client.post(reverse("complete_team_cancel", args=[team_import.public_id]))
        self.assertEqual(Player.objects.count(), 1)
        self.client.post(reverse("complete_team_start"))
        self.assertEqual(SnpTeamImport.objects.filter(status=SnpTeamImport.READY).count(), 1)

    def test_no_button_without_snp_account_or_for_members(self):
        viewer = User.objects.create_user("viewer", password="pass-12345")
        Membership.objects.create(user=viewer, club=self.club, role=Membership.MEMBER)
        self.client.login(username="viewer", password="pass-12345")
        self.assertNotContains(self.client.get(reverse("list_players")), "Completar equipo")
        self.client.post(reverse("complete_team_start"))
        self.client.login(username="admin", password="pass-12345")
        SnpAccount.objects.all().delete()
        self.assertNotContains(self.client.get(reverse("list_players")), "Completar equipo")
        self.assertEqual(Player.objects.count(), 1)

    def test_backoffice_command_uses_team_id_and_ignores_monthly_limit(self):
        from .models import SnpTeamImport
        team_id = self.club.own_team.public_id
        out = StringIO()
        call_command("complete_snp_team", team_id, "--dry-run", stdout=out)
        self.assertIn("Jugadores a añadir: 2 (Maria Jose Gomez Ruiz, Pedro Raposo Bellerin)", out.getvalue())
        self.assertIn("No se añaden porque ya están registrados: 1 (ANA ALVAREZ → Ana Álvarez)", out.getvalue())
        self.assertEqual(Player.objects.count(), 1)

        SnpTeamImport.objects.create(club=self.club, status=SnpTeamImport.DONE, finished_at=timezone.now())
        out = StringIO()
        call_command("complete_snp_team", team_id, stdout=out)
        self.assertIn("Resultado: 2 jugadores añadidos.", out.getvalue())
        self.assertEqual(Player.objects.count(), 3)

        rival = Team.objects.create(club=self.club, name="Rival", location="X")
        with self.assertRaises(CommandError):
            call_command("complete_snp_team", rival.public_id, stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command("complete_snp_team", "TEAnoexiste0000", stdout=StringIO())

    def test_complete_team_is_a_manual_backoffice_job(self):
        from backoffice.jobs import get_spec
        spec = get_spec("complete_snp_team")
        self.assertEqual((spec.schedule, [p.name for p in spec.params]), ("", ["team_id"]))

    def test_edit_player_saves_name_and_last_name(self):
        response = self.client.post(reverse("edit_player", args=[self.ana.public_id]), {
            "name": "Ana María", "last_name": "Álvarez Ruiz", "position": "Revés", "skillfull_hand": "Diestro",
            "joined_season": "2026-2027", "in_team": "on",
        })
        self.assertRedirects(response, reverse("list_players"))
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.name, self.ana.last_name), ("Ana María", "Álvarez Ruiz"))
        self.assertContains(self.client.get(reverse("edit_player", args=[self.ana.public_id])), 'name="last_name"')
