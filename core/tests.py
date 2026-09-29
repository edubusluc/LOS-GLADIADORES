import datetime
import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from call.models import Call
from core.models import Club, Membership
from core.services import create_club
from match.models import Match, Game
from players.models import Player
from post.models import Post
from team.models import Team

User = get_user_model()


class ClubIsolationTests(TestCase):
    """Cada club solo ve y gestiona sus propios datos."""

    def setUp(self):
        self.user_a = User.objects.create_user("admin_a", password="pass-a-12345")
        self.user_b = User.objects.create_user("admin_b", password="pass-b-12345")
        self.club_a = create_club("Club A", "Sevilla", self.user_a)
        self.club_b = create_club("Club B", "Madrid", self.user_b)

        self.player_a = Player.objects.create(club=self.club_a, name="Ana", last_name="Alpha")
        self.player_b = Player.objects.create(club=self.club_b, name="Bea", last_name="Beta")

        self.rival_a = Team.objects.create(club=self.club_a, name="Rival", location="X", in_group=True)
        self.rival_b = Team.objects.create(club=self.club_b, name="Rival", location="Y", in_group=True)

        self.match_a = Match.objects.create(
            club=self.club_a, local=self.club_a.own_team, visiting=self.rival_a,
            start_date=datetime.date(2025, 10, 1),
        )
        self.match_b = Match.objects.create(
            club=self.club_b, local=self.club_b.own_team, visiting=self.rival_b,
            start_date=datetime.date(2025, 10, 1),
        )
        Post.objects.create(club=self.club_a, title="Post A")
        Post.objects.create(club=self.club_b, title="Post B")

        self.client.login(username="admin_a", password="pass-a-12345")

    def test_create_club_sets_own_team_and_admin(self):
        self.assertEqual(self.club_a.own_team.name, "Club A")
        self.assertTrue(Membership.objects.get(user=self.user_a, club=self.club_a).is_admin)
        self.assertEqual(self.player_a.team, self.club_a.own_team)

    def test_lists_only_show_own_club_data(self):
        players = self.client.get(reverse("list_players")).context["players"]
        self.assertEqual([p.id for p in players], [self.player_a.id])

        teams = self.client.get(reverse("list_teams")).context["teams"]
        self.assertTrue(all(t.club_id == self.club_a.id for t in teams))

        matches = self.client.get(reverse("list_match")).context["matches"]
        self.assertEqual([m.id for m in matches], [self.match_a.id])

        posts = self.client.get(reverse("home")).context["page_obj"]
        self.assertEqual([p.title for p in posts], ["Post A"])

    def test_foreign_objects_return_404(self):
        urls = [
            reverse("show_player", args=[self.player_b.id]),
            reverse("edit_player", args=[self.player_b.id]),
            reverse("edit_team", args=[self.rival_b.id]),
            reverse("call_for_match", args=[self.match_b.id]),
            reverse("create_call", args=[self.match_b.id]),
            reverse("delete_match", args=[self.match_b.id]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

        response = self.client.get(reverse("player_statistics"), {"player": self.player_b.id})
        self.assertEqual(response.status_code, 404)

    def test_player_statistics_only_lists_own_players(self):
        response = self.client.get(reverse("player_statistics"))
        self.assertEqual(list(response.context["players"]), [self.player_a])

    def test_team_statistics_use_own_team(self):
        response = self.client.get(reverse("team_statistics"))
        self.assertEqual(response.context["team"], self.club_a.own_team)
        self.assertEqual([c["player"] for c in response.context["column_chart_data"]], ["Ana Alpha"])

    def test_created_objects_belong_to_active_club(self):
        self.client.post(reverse("create_player"), {
            "name": "Nuevo", "last_name": "Jugador", "position": "NONE", "skillfull_hand": "NONE",
        })
        player = Player.objects.get(name="Nuevo")
        self.assertEqual(player.club, self.club_a)
        self.assertEqual(player.team, self.club_a.own_team)

        self.client.post(reverse("create_team"), {"name": "Otro rival", "location": "Z"})
        self.assertEqual(Team.objects.get(name="Otro rival").club, self.club_a)

    def test_team_name_unique_per_club(self):
        response = self.client.post(reverse("create_team"), {"name": "rival", "location": "Z"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Team.objects.filter(club=self.club_a, name__iexact="rival").count(), 1)

    def test_cannot_create_match_with_foreign_teams(self):
        response = self.client.post(reverse("create_match"), {
            "local": self.club_a.own_team.id, "visiting": self.rival_b.id, "start_date": "2025-11-01",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Match.objects.filter(visiting=self.rival_b, club=self.club_a).exists())

    def test_match_requires_own_team(self):
        other = Team.objects.create(club=self.club_a, name="Otro", location="Z", in_group=True)
        self.client.post(reverse("create_match"), {
            "local": other.id, "visiting": self.rival_a.id, "start_date": "2025-11-01",
        })
        self.assertEqual(Match.objects.filter(club=self.club_a).count(), 1)

        self.client.post(reverse("create_match"), {
            "local": self.rival_a.id, "visiting": self.club_a.own_team.id, "start_date": "2025-11-01",
        })
        self.assertEqual(Match.objects.filter(club=self.club_a).count(), 2)

    def test_call_ignores_foreign_players(self):
        self.client.post(reverse("create_call", args=[self.match_a.id]), {
            "players": [self.player_a.id, self.player_b.id],
        })
        call = Call.objects.get(match=self.match_a)
        self.assertEqual(list(call.players.all()), [self.player_a])

    def test_create_games_uses_own_side(self):
        players = [Player.objects.create(club=self.club_a, name=f"P{i}", last_name="X") for i in range(10)]
        call = Call.objects.create(match=self.match_a, draft_mode=False)
        call.players.set(players)

        ordered = [{"player1Id": players[i].id, "player2Id": players[i + 1].id} for i in range(0, 10, 2)]
        import json
        self.client.post(reverse("create_game", args=[self.match_a.id]), {"ordered_games": json.dumps(ordered)})
        games = Game.objects.filter(match=self.match_a)
        self.assertEqual(games.count(), 5)
        self.assertTrue(all(g.player_1_local and g.player_1_visiting is None for g in games))


class RolesAndClubSwitchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass-12345-x")
        self.viewer = User.objects.create_user("viewer", password="pass-12345-x")
        self.club = create_club("Club A", "Sevilla", self.owner)
        Membership.objects.create(user=self.viewer, club=self.club, role=Membership.MEMBER)

    def test_member_can_read_but_not_write(self):
        self.client.login(username="viewer", password="pass-12345-x")
        self.assertEqual(self.client.get(reverse("list_players")).status_code, 200)

        response = self.client.post(reverse("create_player"), {"name": "X", "last_name": "Y"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertFalse(Player.objects.exists())
        self.assertEqual(self.client.get(reverse("club_members")).status_code, 302)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("list_players"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_user_without_club(self):
        User.objects.create_user("lonely", password="pass-12345-x")
        self.client.login(username="lonely", password="pass-12345-x")
        self.assertRedirects(self.client.get(reverse("list_players")), reverse("no_club"))

    def test_switch_club(self):
        other = create_club("Club B", "Madrid", self.owner)
        Player.objects.create(club=other, name="Bea", last_name="Beta")
        self.client.login(username="owner", password="pass-12345-x")

        self.assertEqual(len(self.client.get(reverse("list_players")).context["players"]), 0)
        self.client.post(reverse("switch_club"), {"club_id": other.id})
        self.assertEqual(len(self.client.get(reverse("list_players")).context["players"]), 1)

    def test_cannot_switch_to_club_without_membership(self):
        stranger = User.objects.create_user("stranger", password="pass-12345-x")
        other = create_club("Club B", "Madrid", stranger)
        self.client.login(username="viewer", password="pass-12345-x")
        self.assertEqual(self.client.post(reverse("switch_club"), {"club_id": other.id}).status_code, 404)

    def test_admin_adds_member_and_last_admin_is_protected(self):
        self.client.login(username="owner", password="pass-12345-x")
        self.client.post(reverse("club_members"), {"username": "nuevo", "password": "Otra-Clave-9876", "role": "member"})
        self.assertTrue(Membership.objects.filter(user__username="nuevo", club=self.club).exists())

        owner_membership = Membership.objects.get(user=self.owner, club=self.club)
        self.client.post(reverse("remove_member", args=[owner_membership.id]))
        self.assertTrue(Membership.objects.filter(pk=owner_membership.pk).exists())

    def test_register_club_creates_user_club_and_membership(self):
        response = self.client.post(reverse("register_club"), {
            "name": "Nuevo Club", "location": "Cádiz",
            "username": "fundador", "email": "f@example.com",
            "password1": "Clave-Segura-123", "password2": "Clave-Segura-123",
        })
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        club = Club.objects.get(name="Nuevo Club")
        self.assertTrue(Membership.objects.get(user__username="fundador", club=club).is_admin)
        self.assertEqual(club.own_team.name, "Nuevo Club")


class AssignDefaultClubCommandTests(TestCase):
    def test_assigns_legacy_data(self):
        user = User.objects.create_user("legacy", password="x")
        own = Team.objects.create(name="LOS GLADIADORES", location="Sevilla", in_group=True)
        rival = Team.objects.create(name="Rival", location="X", in_group=True)
        Player.objects.create(name="Old", last_name="Player", team=own)
        Match.objects.create(local=own, visiting=rival, start_date=datetime.date(2024, 10, 1))
        Post.objects.create(title="Old post")

        call_command("assign_default_club", stdout=io.StringIO())
        call_command("assign_default_club", stdout=io.StringIO())  # idempotente

        club = Club.objects.get()
        own.refresh_from_db()
        self.assertTrue(own.is_own)
        self.assertEqual(club.own_team, own)
        self.assertFalse(Team.objects.filter(club__isnull=True).exists())
        self.assertFalse(Player.objects.filter(club__isnull=True).exists())
        self.assertFalse(Match.objects.filter(club__isnull=True).exists())
        self.assertFalse(Post.objects.filter(club__isnull=True).exists())
        self.assertTrue(Membership.objects.get(user=user, club=club).is_admin)
