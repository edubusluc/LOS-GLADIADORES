from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Membership
from core.services import create_club

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
        self.assertIn("Clubes procesados: 2; con error: 0.", out.getvalue())

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

    def test_snp_job_runs_weekly_on_monday_night(self):
        from backoffice.jobs import get_spec
        self.assertEqual(get_spec("update_snp_scores").schedule, "0 23 * * 1")
