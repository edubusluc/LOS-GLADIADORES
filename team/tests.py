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
        self.rival = Team.objects.create(club=self.club, name="CD Tomares", location="X", gender="M", country="ES",
                                         division="500")
        self.client.force_login(self.user)
        self.url = reverse("create_team")
        self.data = {"name": "Tomares", "location": "Tomares", "gender": "F", "country": "ES", "division": "500"}

    def test_gender_country_and_division_are_required(self):
        response = self.client.post(self.url, {"name": "Burguillos", "location": "X"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(name="Burguillos").exists())

    def test_creates_team_with_gender_country_and_division(self):
        response = self.client.post(self.url, {**self.data, "name": "Burguillos", "country": "PT", "division": "grand_slam"})
        self.assertRedirects(response, reverse("list_teams"), fetch_redirect_response=False)
        team = Team.objects.get(name="Burguillos")
        self.assertEqual((team.gender, team.country, team.division, team.club), ("F", "PT", "grand_slam", self.club))

    def test_similar_name_asks_before_creating(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["similar"], ["CD Tomares (Masculino · España · 500)"])
        self.assertContains(response, 'data-open="1"')
        self.assertFalse(Team.objects.filter(name="Tomares").exists())

        response = self.client.post(self.url, {**self.data, "confirm_similar": "1"})
        self.assertRedirects(response, reverse("list_teams"), fetch_redirect_response=False)
        self.assertTrue(Team.objects.filter(name="Tomares").exists())

    def test_check_request_returns_similar_names_without_creating(self):
        response = self.client.post(self.url, self.data, HTTP_X_SIMILAR_CHECK="1")
        self.assertEqual(response.json(), {"valid": True, "similar": ["CD Tomares (Masculino · España · 500)"]})
        response = self.client.post(self.url, {"name": ""}, HTTP_X_SIMILAR_CHECK="1")
        self.assertEqual(response.json(), {"valid": False, "similar": []})
        self.assertFalse(Team.objects.filter(name="Tomares").exists())

    def test_same_name_in_same_division_is_rejected_even_after_confirming(self):
        # Sin distinguir mayúsculas, tildes ni signos, y aunque cambie la categoría
        response = self.client.post(self.url, {**self.data, "name": "C.D. TOMARES", "confirm_similar": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un equipo con ese nombre en esa división")
        self.assertEqual(Team.objects.filter(club=self.club).count(), 2)

    def test_same_name_in_other_division_asks_and_can_be_created(self):
        data = {**self.data, "name": "CD Tomares", "division": "1000"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.context["similar"], ["CD Tomares (Masculino · España · 500)"])
        self.client.post(self.url, {**data, "confirm_similar": "1"})
        self.assertEqual(Team.objects.filter(club=self.club, name="CD Tomares").count(), 2)

    def test_team_without_division_blocks_its_name_in_every_division(self):
        # Equipos creados antes de existir la división (p. ej. el propio del club)
        own = self.club.own_team
        response = self.client.post(self.url, {**self.data, "name": own.name.upper(), "confirm_similar": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Team.objects.filter(club=self.club, name__iexact=own.name).count(), 1)

    def test_editing_a_team_keeps_its_own_name(self):
        response = self.client.post(reverse("edit_team", args=[self.rival.public_id]),
                                    {**self.data, "name": "CD Tomares", "gender": "M"})
        self.assertRedirects(response, reverse("list_teams"), fetch_redirect_response=False)


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
                         {"name": "Club A", "location": "Sevilla", "gender": "F", "country": "IT", "division": "future",
                          "in_group": "on"})
        own = Team.objects.get(pk=club.own_team.pk)
        self.assertEqual((own.gender, own.country), ("F", "IT"))
        player.refresh_from_db()
        self.assertEqual(player.gender, "F")
