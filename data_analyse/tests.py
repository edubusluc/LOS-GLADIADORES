import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.services import create_club
from data_analyse import pairs as pair_stats
from match.models import Game, Match
from players.models import Player
from team.models import Team

User = get_user_model()


class PairStatisticsTests(TestCase):
    """
    Datos controlados (orden cronológico):
      2024-2025  local      A+B gana, A+B gana
      2024-2025  visitante  A+B pierde, C+D gana
      2025-2026  local      A+B gana, C+D pierde
      2025-2026  visitante  A+C gana (C fuera del equipo)
    """

    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.user)
        own = self.club.own_team
        rival = Team.objects.create(club=self.club, name="Rival", location="X", in_group=True)
        mk = lambda n: Player.objects.create(club=self.club, name=n, last_name=f"{n}son")
        self.a, self.b, self.c, self.d = mk("A"), mk("B"), mk("C"), mk("D")
        self.c.in_team = False
        self.c.save()

        def match(date, own_local, games):
            m = Match.objects.create(
                club=self.club, local=own if own_local else rival, visiting=rival if own_local else own,
                start_date=date, draft_mode=False,
            )
            for n, (p1, p2, won) in enumerate(games, start=1):
                side = 'local' if own_local else 'visiting'
                winner = ('Local' if own_local else 'Visitante') if won else ('Visitante' if own_local else 'Local')
                Game.objects.create(match=m, n_game=n, score=3 if n < 3 else 2, winner=winner, draft_mode=False,
                                    **{f'player_1_{side}': p1, f'player_2_{side}': p2})
            return m

        match(datetime.date(2024, 10, 1), True, [(self.a, self.b, True), (self.b, self.a, True)])
        match(datetime.date(2024, 11, 1), False, [(self.a, self.b, False), (self.c, self.d, True)])
        match(datetime.date(2025, 10, 1), True, [(self.a, self.b, True), (self.c, self.d, False)])
        match(datetime.date(2025, 11, 1), False, [(self.a, self.c, True)])

        self.client.login(username="admin", password="pass-12345")

    def test_pair_summary(self):
        s = pair_stats.pair_summary(pair_stats.club_game_log(self.club), self.b.id, self.a.id)
        self.assertEqual((s['played'], s['wins'], s['losses'], s['pct']), (4, 3, 1, 75.0))
        self.assertEqual(s['matches'], 3)
        self.assertEqual((s['local_wins'], s['local_losses']), (3, 0))
        self.assertEqual((s['visiting_wins'], s['visiting_losses']), (0, 1))
        self.assertEqual((s['streak_type'], s['streak_len']), ('V', 1))
        self.assertEqual(s['best_win_streak'], 2)
        self.assertEqual(s['form'], [True, True, False, True])
        self.assertEqual(
            [(r['season'], r['played'], r['wins'], r['pct']) for r in s['seasons']],
            [('2024-2025', 3, 2, 66.7), ('2025-2026', 1, 1, 100.0)],
        )

    def test_top_tables(self):
        log = pair_stats.club_game_log(self.club)
        squad = list(Player.objects.filter(club=self.club, in_team=True))
        local = pair_stats.top_players(log, squad, local=True)
        # A y B: 3 de 3 en casa; D: 0 de 1 (no llega al mínimo); C no está en el equipo.
        self.assertEqual([(r['name'], r['pct']) for r in local], [("A Ason", 100.0), ("B Bson", 100.0)])
        self.assertEqual(pair_stats.top_players(log, squad, local=False), [])  # nadie llega a 3 fuera

        pairs_local = pair_stats.top_pairs(log, squad, local=True)
        self.assertEqual([(r['name'], r['played'], r['pct']) for r in pairs_local], [("A Ason / B Bson", 3, 100.0)])
        self.assertEqual(pair_stats.top_pairs(log, squad, local=False), [])  # A+B solo 1 fuera

    def test_top_tables_respect_season(self):
        log = pair_stats.club_game_log(self.club, "2025-2026")
        squad = list(Player.objects.filter(club=self.club, in_team=True))
        self.assertEqual(pair_stats.top_players(log, squad, local=True), [])  # 1 partido por jugador

    def test_pair_view(self):
        response = self.client.get(reverse("pair_statistics"), {"p1": self.a.id, "p2": self.b.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["s"]["played"], 4)
        self.assertEqual(len(response.context["pairs"]), 3)  # A+B, C+D, A+C

        self.assertEqual(self.client.get(reverse("pair_statistics")).status_code, 200)
        same = self.client.get(reverse("pair_statistics"), {"p1": self.a.id, "p2": self.a.id})
        self.assertIn("error", same.context)

    def test_pair_view_rejects_other_club_players(self):
        other = create_club("Club B", "Madrid", User.objects.create_user("b", password="x"))
        foreign = Player.objects.create(club=other, name="X", last_name="Y")
        response = self.client.get(reverse("pair_statistics"), {"p1": self.a.id, "p2": foreign.id})
        self.assertEqual(response.status_code, 404)

    def test_team_statistics_chart_only_current_players(self):
        response = self.client.get(reverse("team_statistics"))
        names = [row["player"] for row in response.context["column_chart_data"]]
        self.assertNotIn("C Cson", names)
        self.assertIn("A Ason", names)
        self.assertEqual(len(response.context["top_local_players"]), 2)
