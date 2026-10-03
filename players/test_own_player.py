import datetime
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Invitation, Membership, PhotoCheck
from core.services import create_club
from core.test_images import image_bytes
from players.models import Player

User = get_user_model()


def upload(name="foto.jpg"):
    return SimpleUploadedFile(name, image_bytes((600, 600)), content_type="image/jpeg")


class MediaMixin:
    def use_temp_media(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)


class OwnPlayerTests(MediaMixin, TestCase):
    def setUp(self):
        self.use_temp_media()
        self.captain = User.objects.create_user("capitan", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.captain, gender="M")
        self.user = User.objects.create_user("ana", password="pass-12345", email="ana@example.com")
        Membership.objects.create(user=self.user, club=self.club, role=Membership.MEMBER)
        self.ana = Player.objects.create(club=self.club, name="Ana", last_name="Ruiz Gómez", joined_season="2024-2025")
        self.other = Player.objects.create(club=self.club, name="Luis", last_name="Pérez")
        self.client.force_login(self.user)

    def test_joining_with_invitation_goes_to_choose_player(self):
        newcomer = User.objects.create_user("nuevo", password="pass-12345")
        invitation = Invitation.objects.create(club=self.club, created_by=self.captain)
        self.client.force_login(newcomer)
        response = self.client.post(reverse("invitation", args=[invitation.token]))
        self.assertRedirects(response, reverse("my_player"), fetch_redirect_response=False)
        page = self.client.get(reverse("my_player"))
        self.assertContains(page, "ANA RUIZ GÓMEZ")
        self.assertContains(page, "Soy yo")

    def test_link_to_existing_player(self):
        response = self.client.post(reverse("link_player", args=[self.ana.public_id]))
        self.assertRedirects(response, reverse("my_player"), fetch_redirect_response=False)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.user, self.user)
        # Ya enlazado: «Mi jugador» es el formulario de su perfil y no puede enlazar otro.
        self.assertContains(self.client.get(reverse("my_player")), "Editar mi perfil")
        self.client.post(reverse("link_player", args=[self.other.public_id]))
        self.other.refresh_from_db()
        self.assertIsNone(self.other.user)

    def test_cannot_take_player_linked_to_someone_else(self):
        intruder = User.objects.create_user("otro", password="pass-12345")
        Membership.objects.create(user=intruder, club=self.club, role=Membership.MEMBER)
        self.ana.user = intruder
        self.ana.save()
        self.client.post(reverse("link_player", args=[self.ana.public_id]))
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.user, intruder)
        self.assertNotContains(self.client.get(reverse("my_player")), "ANA RUIZ")

    def test_cannot_link_player_of_another_club(self):
        other_captain = User.objects.create_user("c2", password="pass-12345")
        other_club = create_club("Club B", "Huelva", other_captain)
        foreign = Player.objects.create(club=other_club, name="Eva", last_name="Sanz")
        response = self.client.post(reverse("link_player", args=[foreign.public_id]))
        self.assertEqual(response.status_code, 404)

    def test_create_own_player(self):
        response = self.client.post(reverse("my_player"), {
            "name": "Marta", "last_name": "López", "position": "Revés", "skillfull_hand": "Zurdo", "photo": upload(),
        })
        player = Player.objects.get(name="Marta")
        self.assertRedirects(response, reverse("show_player", args=[player.public_id]), fetch_redirect_response=False)
        self.assertEqual((player.user, player.club, player.team, player.in_team), (self.user, self.club, self.club.own_team, True))
        self.assertTrue(player.photo.name.startswith("players/"))

    def test_create_own_player_blocks_same_name(self):
        response = self.client.post(reverse("my_player"), {
            "name": "ana", "last_name": "Ruiz Gomez", "position": "NONE", "skillfull_hand": "NONE",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un jugador con ese nombre")
        self.assertEqual(Player.objects.filter(club=self.club).count(), 2)

    def test_linked_player_edits_position_hand_and_photo_but_not_name_or_season(self):
        self.ana.user = self.user
        self.ana.save()
        response = self.client.post(reverse("my_player"), {
            "position": "Derecha", "skillfull_hand": "Zurdo", "photo": upload(),
            "name": "Otro", "last_name": "Nombre", "joined_season": "2020-2021",
        })
        self.assertRedirects(response, reverse("show_player", args=[self.ana.public_id]), fetch_redirect_response=False)
        self.ana.refresh_from_db()
        self.assertEqual((self.ana.position, self.ana.skillfull_hand), ("Derecha", "Zurdo"))
        self.assertEqual((self.ana.name, self.ana.last_name, self.ana.joined_season), ("Ana", "Ruiz Gómez", "2024-2025"))
        self.assertTrue(self.ana.photo.name.startswith("players/"))
        check = PhotoCheck.objects.get(player=self.ana)
        self.assertEqual((check.uploaded_by, check.photo, check.club), (self.user, self.ana.photo.name, self.club))

    def test_member_cannot_use_captain_edit(self):
        self.ana.user = self.user
        self.ana.save()
        self.client.post(reverse("edit_player", args=[self.ana.public_id]), {"name": "X", "last_name": "Y"})
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.name, "Ana")

    def test_captain_unlinks(self):
        self.ana.user = self.user
        self.ana.save()
        self.client.force_login(self.captain)
        self.assertContains(self.client.get(reverse("edit_player", args=[self.ana.public_id])), "ana@example.com")
        self.client.post(reverse("unlink_player", args=[self.ana.public_id]))
        self.ana.refresh_from_db()
        self.assertIsNone(self.ana.user)

    def test_member_cannot_unlink(self):
        self.ana.user = self.user
        self.ana.save()
        self.client.post(reverse("unlink_player", args=[self.ana.public_id]))
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.user, self.user)


REKOGNITION_ON = dict(
    REKOGNITION_ACCESS_KEY_ID="key", REKOGNITION_SECRET_ACCESS_KEY="secret",
    REKOGNITION_FREE_UNTIL=datetime.date(2099, 1, 1), REKOGNITION_MONTHLY_LIMIT=2,
)


class PhotoModerationTests(MediaMixin, TestCase):
    def setUp(self):
        self.use_temp_media()
        self.captain = User.objects.create_user("capitan", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.captain)
        self.player = Player.objects.create(club=self.club, name="Ana", last_name="Ruiz", user=self.captain)
        self.client.force_login(self.captain)
        patcher = mock.patch("core.moderation._client")
        self.client_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.detect = self.client_mock.return_value.detect_moderation_labels
        self.detect.return_value = {"ModerationLabels": []}

    def post_photo(self):
        return self.client.post(reverse("my_player"), {"position": "NONE", "skillfull_hand": "NONE", "photo": upload()})

    @override_settings(**REKOGNITION_ON)
    def test_clean_photo_is_approved(self):
        self.post_photo()
        self.player.refresh_from_db()
        self.assertTrue(self.player.photo)
        check = PhotoCheck.objects.get()
        self.assertEqual((check.status, check.api_called), (PhotoCheck.APPROVED, True))
        # Se envía en JPEG (Rekognition no admite WebP).
        sent = self.detect.call_args.kwargs["Image"]["Bytes"]
        self.assertTrue(sent.startswith(b"\xff\xd8"))

    @override_settings(**REKOGNITION_ON)
    def test_sensitive_photo_is_rejected_and_not_saved(self):
        self.detect.return_value = {"ModerationLabels": [
            {"Name": "Exposed Female Nipple", "ParentName": "Explicit Nudity", "Confidence": 97.0},
        ]}
        response = self.post_photo()
        self.assertContains(response, "no se puede usar")
        self.player.refresh_from_db()
        self.assertFalse(self.player.photo)
        check = PhotoCheck.objects.get()
        self.assertEqual((check.status, check.photo), (PhotoCheck.REJECTED, ""))
        self.assertIn("Exposed Female Nipple", check.reason)

    @override_settings(**REKOGNITION_ON)
    def test_harmless_labels_are_allowed(self):
        self.detect.return_value = {"ModerationLabels": [
            {"Name": "Swimwear or Underwear", "ParentName": "", "Confidence": 90.0},
        ]}
        self.post_photo()
        self.assertEqual(PhotoCheck.objects.get().status, PhotoCheck.APPROVED)

    @override_settings(**REKOGNITION_ON)
    def test_monthly_free_limit_stops_calling_aws(self):
        self.post_photo()
        self.post_photo()
        self.post_photo()
        self.assertEqual(self.detect.call_count, 2)
        last = PhotoCheck.objects.order_by("-id").first()
        self.assertEqual(last.status, PhotoCheck.UNCHECKED)
        self.assertIn("Límite gratuito", last.reason)
        self.player.refresh_from_db()
        self.assertEqual(self.player.photo.name, last.photo)

    @override_settings(**{**REKOGNITION_ON, "REKOGNITION_FREE_UNTIL": datetime.date(2020, 1, 1)})
    def test_after_free_period_photos_are_unchecked(self):
        self.post_photo()
        self.detect.assert_not_called()
        self.assertIn("Periodo gratuito terminado", PhotoCheck.objects.get().reason)

    def test_not_configured_photos_are_unchecked(self):
        self.post_photo()
        self.detect.assert_not_called()
        self.assertEqual(PhotoCheck.objects.get().status, PhotoCheck.UNCHECKED)

    @override_settings(**REKOGNITION_ON)
    def test_aws_error_accepts_photo_unchecked(self):
        self.detect.side_effect = RuntimeError("sin red")
        self.post_photo()
        check = PhotoCheck.objects.get()
        self.assertEqual(check.status, PhotoCheck.UNCHECKED)
        self.assertIn("sin red", check.reason)
        self.player.refresh_from_db()
        self.assertTrue(self.player.photo)


class BackofficePhotoTests(MediaMixin, TestCase):
    def setUp(self):
        self.use_temp_media()
        self.captain = User.objects.create_user("capitan", password="pass-12345")
        self.club = create_club("Club A", "Sevilla", self.captain)
        self.player = Player.objects.create(club=self.club, name="Ana", last_name="Ruiz", user=self.captain)
        self.client.force_login(self.captain)
        self.client.post(reverse("my_player"), {"position": "NONE", "skillfull_hand": "NONE", "photo": upload()})
        self.player.refresh_from_db()
        self.check = PhotoCheck.objects.get()
        self.staff = User.objects.create_user("staff", password="pass-12345", is_staff=True)
        self.client.force_login(self.staff)

    def test_unchecked_photos_are_listed(self):
        response = self.client.get(reverse("backoffice:photo_list"))
        self.assertContains(response, self.player.photo.url)
        self.assertContains(response, "Rekognition no está configurado")

    def test_not_staff_gets_404(self):
        self.client.force_login(self.captain)
        self.assertEqual(self.client.get(reverse("backoffice:photo_list")).status_code, 404)

    def test_delete_photo(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("backoffice:photo_delete", args=[self.check.public_id]))
        self.player.refresh_from_db()
        self.assertFalse(self.player.photo)
        self.assertFalse(PhotoCheck.objects.exists())

    def test_mark_reviewed(self):
        self.client.post(reverse("backoffice:photo_reviewed", args=[self.check.public_id]))
        self.check.refresh_from_db()
        self.assertEqual(self.check.status, PhotoCheck.REVIEWED)

    def test_delete_all_photos_of_user(self):
        self.assertContains(self.client.get(reverse("backoffice:user_detail", args=[self.captain.pk])), "Eliminar todas sus fotos")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("backoffice:user_photos_delete", args=[self.captain.pk]))
        self.player.refresh_from_db()
        self.assertFalse(self.player.photo)


class InvitationJoinRedirectTests(TestCase):
    def test_expired_link_does_not_go_to_player_choice(self):
        captain = User.objects.create_user("capitan", password="pass-12345")
        club = create_club("Club A", "Sevilla", captain)
        invitation = Invitation.objects.create(club=club, created_by=captain, expires_at=timezone.now())
        self.client.force_login(User.objects.create_user("x", password="pass-12345"))
        response = self.client.post(reverse("invitation", args=[invitation.token]))
        self.assertEqual(response.status_code, 410)
