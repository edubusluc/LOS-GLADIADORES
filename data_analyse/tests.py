import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.services import create_club
from data_analyse import pairs as pair_stats
from match.models import Game, Match, Result
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

    def test_hot_streaks(self):
        """A encadena 2 victorias; ninguna pareja del equipo llega al mínimo (C está fuera)."""
        squad = list(Player.objects.filter(club=self.club, in_team=True))
        player, pair = pair_stats.hot_streaks(pair_stats.club_game_log(self.club), squad)
        self.assertEqual((player['player'], player['streak']), (self.a, 2))
        self.assertIsNone(pair)

        # Con C en la lista, A+C (1 victoria) sigue sin llegar; C+D va perdiendo
        everyone = list(Player.objects.filter(club=self.club))
        self.assertIsNone(pair_stats.hot_streaks(pair_stats.club_game_log(self.club), everyone)[1])

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
        # Con una pareja elegida ya no se muestra el listado de parejas destacadas
        self.assertNotContains(response, "Parejas destacadas")

        overview = self.client.get(reverse("pair_statistics"))
        self.assertEqual(overview.status_code, 200)
        self.assertContains(overview, "Parejas destacadas")
        same = self.client.get(reverse("pair_statistics"), {"p1": self.a.id, "p2": self.a.id})
        self.assertIn("error", same.context)

    def test_best_and_worst_pairs(self):
        # A+B 3/4 y C+D 1/2; A+C solo 1 partido, no llega al mínimo
        response = self.client.get(reverse("pair_statistics"))
        key = lambda rows: [(r["p1"].name, r["p2"].name, r["played"], r["pct"]) for r in rows]
        self.assertEqual(key(response.context["best_pairs"]), [("A", "B", 4, 75.0)])
        self.assertEqual(key(response.context["worst_pairs"]), [("C", "D", 2, 50.0)])

    def test_best_and_worst_pairs_ranking(self):
        row = lambda name, played, wins: {'name': name, 'played': played, 'wins': wins,
                                          'pct': pair_stats._pct(wins, played)}
        pairs = [row('a', 10, 9), row('b', 5, 1), row('c', 4, 4), row('d', 6, 3),
                 row('e', 8, 2), row('f', 3, 2), row('g', 1, 0), row('h', 7, 5)]
        best, worst = pair_stats.best_and_worst_pairs(pairs)
        self.assertEqual([r['name'] for r in best], ['c', 'a', 'h'])
        self.assertEqual([r['name'] for r in worst], ['b', 'e', 'd'])  # 'g' no llega al mínimo

        # Con pocas parejas se reparten sin repetir: 3 parejas -> 2 mejores y 1 peor
        best, worst = pair_stats.best_and_worst_pairs(pairs[:3])
        self.assertEqual(([r['name'] for r in best], [r['name'] for r in worst]), (['c', 'a'], ['b']))

    def test_pair_last_games(self):
        # Cinco partidos más de A+B: la tabla muestra solo los cinco más recientes
        own, rival = self.club.own_team, Team.objects.get(club=self.club, name="Rival")
        for day in range(1, 6):
            m = Match.objects.create(club=self.club, local=own, visiting=rival,
                                     start_date=datetime.date(2026, 1, day), draft_mode=False)
            Game.objects.create(match=m, n_game=1, score=3, winner='Visitante', draft_mode=False,
                                player_1_local=self.b, player_2_local=self.a)
        response = self.client.get(reverse("pair_statistics"), {"p1": self.a.id, "p2": self.b.id})
        games = response.context["last_games"]
        self.assertEqual([g["date"] for g in games], [datetime.date(2026, 1, d) for d in (5, 4, 3, 2, 1)])
        self.assertTrue(all(g["local"] and not g["won"] and g["rival"] == rival for g in games))
        self.assertContains(response, "Últimos 5 partidos")

    def test_pair_last_games_sets_and_side(self):
        m = Match.objects.get(start_date=datetime.date(2024, 11, 1))
        Result.objects.create(game=m.games.get(n_game=1), set1_local=6, set1_visiting=3,
                              set2_local=6, set2_visiting=4)
        response = self.client.get(reverse("pair_statistics"), {"p1": self.b.id, "p2": self.a.id})
        games = response.context["last_games"]
        self.assertEqual([(g["date"], g["n_game"], g["local"], g["won"]) for g in games], [
            (datetime.date(2025, 10, 1), 1, True, True),
            (datetime.date(2024, 11, 1), 1, False, False),
            (datetime.date(2024, 10, 1), 2, True, True),
            (datetime.date(2024, 10, 1), 1, True, True),
        ])
        self.assertEqual(games[1]["sets"], "3-6 4-6")

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

    def test_player_season_games_table(self):
        response = self.client.get(reverse("player_statistics"), {"player": self.a.id, "season": "2024-2025"})
        games = response.context["d"]["games"]
        # Del más reciente al más antiguo: visitante (1 nov) y luego los 2 partidos en casa (1 oct)
        self.assertEqual(
            [(g["date"], g["n_game"], g["local"], g["won"], g["points"]) for g in games],
            [
                (datetime.date(2024, 11, 1), 1, False, False, 0),
                (datetime.date(2024, 10, 1), 1, True, True, 3),
                (datetime.date(2024, 10, 1), 2, True, True, 3),
            ],
        )
        self.assertEqual(games[0]["partner"], self.b)
        self.assertEqual(games[0]["rival"].name, "Rival")

        # Cada fila enlaza a su partido en la sección de partidos
        match_id = games[0]["match_id"]
        self.assertContains(response, f'{reverse("call_for_match", args=[match_id])}#partido-1')
        self.assertContains(self.client.get(reverse("call_for_match", args=[match_id])), 'id="partido-1"')

    def test_player_season_games_show_sets_from_player_side(self):
        m = Match.objects.get(start_date=datetime.date(2024, 11, 1))
        game = m.games.get(n_game=1)  # A+B de visitantes, pierden
        Result.objects.create(game=game, set1_local=6, set1_visiting=3, set2_local=6, set2_visiting=4)
        response = self.client.get(reverse("player_statistics"), {"player": self.a.id, "season": "2024-2025"})
        self.assertEqual(response.context["d"]["games"][0]["sets"], "3-6 4-6")

    def test_player_season_games_empty_and_only_selected_season(self):
        response = self.client.get(reverse("player_statistics"), {"player": self.d.id, "season": "2025-2026"})
        self.assertEqual([g["n_game"] for g in response.context["d"]["games"]], [2])
        self.assertIsNone(self.client.get(reverse("player_statistics"), {"player": self.d.id}).context["d"])

        e = Player.objects.create(club=self.club, name="E", last_name="Eson")
        response = self.client.get(reverse("player_statistics"), {"player": e.id, "season": "2025-2026"})
        self.assertEqual(response.context["d"]["games"], [])
        self.assertContains(response, "No jugó ningún partido esta temporada.")
