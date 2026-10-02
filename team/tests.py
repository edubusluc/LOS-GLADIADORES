from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.services import create_club
from core.similarity import is_similar
from players.models import Player
from .models import Team

User = get_user_model()


class SimilarNameTests(SimpleTestCase):
    def test_same_name_ignoring_case_accents_and_punctuation(self):
        self.assertTrue(is_similar("Pádel Tomares", "padel tomares"))
        self.assertTrue(is_similar("C.D. Tomares", "CD Tomares"))

    def test_contained_or_typo(self):
        self.assertTrue(is_similar("Tomares", "CD Tomares"))
        self.assertTrue(is_similar("Los Gladiadores", "Los Gladiadore"))
        self.assertTrue(is_similar("Juan Pérez", "Juan Perez García", min_subset_tokens=2))

    def test_different_names(self):
        self.assertFalse(is_similar("Tomares", "Burguillos"))
        self.assertFalse(is_similar("Juan Pérez", "Pedro Pérez", min_subset_tokens=2))
        # Un nombre de pila suelto no basta para avisar de todos los Juanes
        self.assertFalse(is_similar("Juan", "Juan Pérez García", min_subset_tokens=2))


class CreateTeamTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.user, gender="F", country="ES")
        self.rival = Team.objects.create(club=self.club, name="CD Tomares", location="X", gender="M", country="ES")
        self.client.force_login(self.user)
        self.url = reverse("create_team")
        self.data = {"name": "Tomares", "location": "Tomares", "gender": "F", "country": "ES"}

    def test_gender_and_country_are_required(self):
        response = self.client.post(self.url, {"name": "Burguillos", "location": "X"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(name="Burguillos").exists())

    def test_creates_team_with_gender_and_country(self):
        response = self.client.post(self.url, {**self.data, "name": "Burguillos", "country": "PT"})
        self.assertRedirects(response, reverse("list_teams"), fetch_redirect_response=False)
        team = Team.objects.get(name="Burguillos")
        self.assertEqual((team.gender, team.country, team.club), ("F", "PT", self.club))

    def test_similar_name_asks_before_creating(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["similar"], ["CD Tomares (Masculino · España)"])
        self.assertContains(response, 'data-open="1"')
        self.assertFalse(Team.objects.filter(name="Tomares").exists())

        response = self.client.post(self.url, {**self.data, "confirm_similar": "1"})
        self.assertRedirects(response, reverse("list_teams"), fetch_redirect_response=False)
        self.assertTrue(Team.objects.filter(name="Tomares").exists())

    def test_check_request_returns_similar_names_without_creating(self):
        response = self.client.post(self.url, self.data, HTTP_X_SIMILAR_CHECK="1")
        self.assertEqual(response.json(), {"valid": True, "similar": ["CD Tomares (Masculino · España)"]})
        response = self.client.post(self.url, {"name": ""}, HTTP_X_SIMILAR_CHECK="1")
        self.assertEqual(response.json(), {"valid": False, "similar": []})
        self.assertFalse(Team.objects.filter(name="Tomares").exists())

    def test_same_name_allowed_for_other_gender_but_not_identical_team(self):
        data = {**self.data, "name": "CD Tomares", "confirm_similar": "1"}
        self.client.post(self.url, data)
        self.assertEqual(Team.objects.filter(club=self.club, name="CD Tomares").count(), 2)

        response = self.client.post(self.url, {**data, "name": "cd tomares", "gender": "M"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Team.objects.filter(club=self.club, name__iexact="CD Tomares").count(), 2)


class TeamGenderPropagationTests(TestCase):
    def test_players_take_the_gender_of_their_team(self):
        user = User.objects.create_user("admin", password="pass-12345")
        club = create_club("Club A", "Sevilla", user, gender="F", country="ES")
        player = Player.objects.create(club=club, name="Ana", last_name="López")
        self.assertEqual(player.gender, "F")

        own = club.own_team
        own.gender = "M"
        own.save()
        player.refresh_from_db()
        self.assertEqual(player.gender, "M")

    def test_edit_team_saves_gender_and_country(self):
        user = User.objects.create_user("admin", password="pass-12345")
        club = create_club("Club A", "Sevilla", user)
        player = Player.objects.create(club=club, name="Ana", last_name="López")
        self.client.force_login(user)
        self.client.post(reverse("edit_team", args=[club.own_team.public_id]),
                         {"name": "Club A", "location": "Sevilla", "gender": "F", "country": "IT", "in_group": "on"})
        own = Team.objects.get(pk=club.own_team.pk)
        self.assertEqual((own.gender, own.country), ("F", "IT"))
        player.refresh_from_db()
        self.assertEqual(player.gender, "F")
