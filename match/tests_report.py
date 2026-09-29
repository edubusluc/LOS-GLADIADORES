import datetime
import re
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from call.models import Call
from core.models import Membership
from core.services import create_club
from data_analyse.pairs import club_game_log
from match import advisor
from match.models import Game, Match
from match.report import build_report
from match.report_pdf import render_report
from players.models import Player
from team.models import Team

User = get_user_model()


def pdf_pages(data):
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


class AdvisorTests(TestCase):
    def test_win_probability_follows_snp_scoring(self):
        # Ganar seguro los dos de 3 puntos y perder los de 2 = 6 puntos: empate (media victoria)
        win, expected = advisor.win_probability([1, 1, 0, 0, 0])
        self.assertAlmostEqual(win, 0.5)
        self.assertEqual(expected, 6)
        # Ganar los de 3 puntos y uno de 2 = 8 puntos: victoria
        self.assertAlmostEqual(advisor.win_probability([1, 1, 1, 0, 0])[0], 1.0)
        # Ganar solo los tres de 2 puntos = 6: empate
        self.assertAlmostEqual(advisor.win_probability([0, 0, 1, 1, 1])[0], 0.5)
        self.assertAlmostEqual(advisor.win_probability([0.5] * 5)[0], 0.5)


class ReportTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="pass-12345", email="capitan@example.com")
        self.club = create_club("Club A", "Sevilla", self.admin)
        self.viewer = User.objects.create_user("viewer", password="pass-12345", email="viewer@example.com")
        Membership.objects.create(user=self.viewer, club=self.club, role=Membership.MEMBER)
        self.rival = Team.objects.create(club=self.club, name="Rival", location="X", in_group=True)
        positions = ["Derecha", "Revés"]
        self.players = [
            Player.objects.create(club=self.club, name=f"Jugador{i}", last_name="Apellido Muy Largo",
                                  snp_score=20 + i * 3, position=positions[i % 2])
            for i in range(20)
        ]
        # Historial: dos enfrentamientos cerrados como visitante contra el mismo rival
        for day, winner in ((1, "Visitante"), (8, "Local")):
            m = Match.objects.create(club=self.club, local=self.rival, visiting=self.club.own_team,
                                     start_date=datetime.date(2025, 10, day), draft_mode=False,
                                     result="Victoria Visitante" if winner == "Visitante" else "Victoria Local",
                                     result_points="3/9" if winner == "Visitante" else "9/3")
            for n in range(1, 6):
                Game.objects.create(match=m, n_game=n, score=3 if n < 3 else 2, winner=winner, draft_mode=False,
                                    player_1_visiting=self.players[2 * n - 2], player_2_visiting=self.players[2 * n - 1])
        self.match = Match.objects.create(club=self.club, local=self.rival, visiting=self.club.own_team,
                                          start_date=datetime.date(2025, 11, 1))
        self.call = Call.objects.create(match=self.match)
        self.call.players.set(self.players)
        self.client.login(username="admin", password="pass-12345")

    def test_report_uses_venue_and_recommends_valid_lineups(self):
        report = build_report(self.call)
        self.assertEqual(report["venue_label"], "visitante")
        self.assertEqual(len(report["precedents"]), 2)
        self.assertEqual(len(report["lineups"]), 2)
        for item in report["lineups"]:
            lineup = item["lineup"]
            players = [f.id for p in lineup.pairs for f in (p.a, p.b)]
            self.assertEqual(len(set(players)), 10)                      # 10 jugadores distintos
            self.assertTrue(set(players) <= {p.id for p in self.players})  # todos convocados
            sums = [p.snp_sum for p in lineup.pairs]
            self.assertEqual(sums, sorted(sums, reverse=True))             # orden oficial SNP
            sentences = [s for s in re.split(r"(?<=[.)])\s+(?=[A-ZÁÉÍÓÚ])", item["explanation"]) if s]
            self.assertLessEqual(len(sentences), 4)
        a, b = (item["lineup"] for item in report["lineups"])
        self.assertGreaterEqual(len(b.keys - a.keys), 1)

    def test_pdf_fits_in_two_pages_with_many_players(self):
        pdf = render_report(build_report(self.call))
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(pdf_pages(pdf), 2)

    def test_not_enough_players(self):
        self.call.players.set(self.players[:6])
        report = build_report(self.call)
        self.assertEqual(report["lineups"], [])
        self.assertEqual(pdf_pages(render_report(report)), 2)

    def test_closing_call_emails_report_to_admins_only(self):
        self.client.post(reverse("close_call", args=[self.match.id]))
        self.call.refresh_from_db()
        self.assertFalse(self.call.draft_mode)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["capitan@example.com"])
        name, content, mimetype = message.attachments[0]
        self.assertEqual(mimetype, "application/pdf")
        self.assertTrue(content.startswith(b"%PDF"))

    def test_email_failure_does_not_block_closing(self):
        with mock.patch("match.views.send_call_report", side_effect=OSError("SMTP caído")):
            response = self.client.post(reverse("close_call", args=[self.match.id]), follow=True)
        self.call.refresh_from_db()
        self.assertFalse(self.call.draft_mode)
        self.assertContains(response, "no se pudo enviar el informe")

    def test_manual_download_is_admin_only(self):
        response = self.client.get(reverse("call_report", args=[self.match.id]))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.client.login(username="viewer", password="pass-12345")
        self.assertEqual(self.client.get(reverse("call_report", args=[self.match.id])).status_code, 302)

    def test_report_ignores_matches_after_its_date(self):
        old = Match.objects.create(club=self.club, local=self.rival, visiting=self.club.own_team,
                                   start_date=datetime.date(2025, 9, 1))
        call = Call.objects.create(match=old)
        call.players.set(self.players)
        report = build_report(call)
        self.assertEqual(report["precedents"], [])
        self.assertTrue(all(f.played == 0 for f in report["players"]))
