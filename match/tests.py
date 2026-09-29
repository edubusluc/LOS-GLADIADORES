import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from call.models import Call
from core.services import create_club
from match.models import Game, Match, Result
from players.models import Player
from players.views import calculate_score as player_performance
from team.models import Team

User = get_user_model()


class CloseMatchUpdatesPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.user)
        rival = Team.objects.create(club=self.club, name="Rival", location="X", in_group=True)
        self.players = [Player.objects.create(club=self.club, name=f"P{i}", last_name="X", score=5) for i in range(10)]
        self.match = Match.objects.create(club=self.club, local=self.club.own_team, visiting=rival,
                                          start_date=datetime.date(2025, 10, 1))
        call = Call.objects.create(match=self.match, draft_mode=False)
        call.players.set(self.players)
        for n in range(1, 6):
            game = Game.objects.create(
                match=self.match, n_game=n, score=3 if n < 3 else 2, winner="Local",
                player_1_local=self.players[2 * n - 2], player_2_local=self.players[2 * n - 1],
            )
            Result.objects.create(game=game, set1_local="6", set1_visiting="2", set2_local="6",
                                  set2_visiting="3", set3_local="0", set3_visiting="0")
        self.client.login(username="admin", password="pass-12345")

    def test_closing_match_recalculates_performance_of_its_players(self):
        self.client.post(reverse("close_match", args=[self.match.id]))
        self.match.refresh_from_db()
        self.assertFalse(self.match.draft_mode)
        for p in self.players:
            p.refresh_from_db()
            self.assertEqual(p.score, player_performance(p))
            self.assertEqual(p.score, 10)  # una victoria de una: rendimiento máximo


class MatchesAndCallsTests(TestCase):
    def setUp(self):
        from core.models import Membership
        from penalty.models import Penalty
        from players.models import current_season
        self.Penalty = Penalty
        self.user = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.user)
        self.viewer = User.objects.create_user("viewer", password="pass-12345")
        Membership.objects.create(user=self.viewer, club=self.club, role=Membership.MEMBER)
        self.rival = Team.objects.create(club=self.club, name="Rival", location="X", in_group=True)
        start = int(current_season()[:4])
        self.current = Match.objects.create(club=self.club, local=self.club.own_team, visiting=self.rival,
                                            start_date=datetime.date(start, 10, 1))
        self.old = Match.objects.create(club=self.club, local=self.club.own_team, visiting=self.rival,
                                        start_date=datetime.date(start - 2, 10, 1))
        self.zoe = Player.objects.create(club=self.club, name="Zoe", last_name="Z")
        self.ana = Player.objects.create(club=self.club, name="Ana", last_name="A")
        self.gone = Player.objects.create(club=self.club, name="Bea", last_name="B", in_team=False)
        self.client.login(username="admin", password="pass-12345")

    def test_match_list_defaults_to_current_season(self):
        response = self.client.get(reverse("list_match"))
        self.assertEqual([m.id for m in response.context["matches"]], [self.current.id])
        response = self.client.get(reverse("list_match"), {"season": "all"})
        self.assertEqual(len(response.context["matches"]), 2)

    def test_call_players_are_alphabetical_and_current(self):
        response = self.client.get(reverse("create_call", args=[self.current.id]))
        self.assertEqual([p.name for p in response.context["players"]], ["Ana", "Zoe"])

    def test_penalties_only_for_current_players(self):
        call = Call.objects.create(match=self.current, draft_mode=False)
        call.players.set([self.ana])
        response = self.client.get(reverse("view_call_log", args=[call.id]))
        self.assertEqual([p.name for p in response.context["players"]], ["Ana", "Zoe"])

        # Zoe no está convocada pero sí en el equipo: se la puede sancionar; Bea ya no está.
        self.client.post(reverse("create_penalty", args=[call.id]), {"players": [self.zoe.id, self.gone.id]})
        self.assertEqual(list(self.Penalty.objects.values_list("player__name", flat=True)), ["Zoe"])

    def test_warnings_view_is_admin_only(self):
        call = Call.objects.create(match=self.current, draft_mode=False)
        self.Penalty.objects.create(player=self.ana, call=call, reason="Advertencia")
        response = self.client.get(reverse("warnings_statistics"))
        self.assertEqual(response.context["total"], 1)
        self.assertEqual(self.client.get(reverse("warnings_statistics"), {"season": "1999-2000"}).context["total"], 0)

        self.client.login(username="viewer", password="pass-12345")
        self.assertEqual(self.client.get(reverse("warnings_statistics")).status_code, 302)

    def test_manage_roster_updates_many_players_at_once(self):
        self.client.post(reverse("manage_roster"), {"in_team": [self.ana.id, self.gone.id]})
        states = dict(Player.objects.values_list("name", "in_team"))
        self.assertEqual(states, {"Ana": True, "Bea": True, "Zoe": False})

        self.client.login(username="viewer", password="pass-12345")
        self.client.post(reverse("manage_roster"), {"in_team": []})
        self.assertEqual(Player.objects.filter(in_team=True).count(), 2)
