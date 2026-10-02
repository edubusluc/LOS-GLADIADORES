import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.emails import LOGO_CID, send_welcome_email
from core.models import Club, Invitation, Membership
from core.services import create_club

User = get_user_model()

SIGNUP = {
    "username": "nuevo", "email": "nuevo@example.com",
    "password1": "Clave-Segura-123", "password2": "Clave-Segura-123",
}

GOOGLE_ON = dict(
    GOOGLE_LOGIN_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS={"google": {"APPS": [{"client_id": "id", "secret": "secret", "key": ""}]}},
)


class InvitationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("capitan", password="pass-12345", email="capitan@example.com")
        self.club = create_club("Club A", "Sevilla", self.admin)
        self.viewer = User.objects.create_user("viewer", password="pass-12345")
        Membership.objects.create(user=self.viewer, club=self.club, role=Membership.MEMBER)

    def invite(self, **kwargs):
        return Invitation.objects.create(club=self.club, created_by=self.admin, **kwargs)

    def url(self, invitation):
        return reverse("invitation", args=[invitation.token])

    # --- Creación y gestión ------------------------------------------------

    def test_admin_creates_invitation_valid_for_24_hours(self):
        self.client.login(username="capitan", password="pass-12345")
        self.client.post(reverse("create_invitation"))
        invitation = Invitation.objects.get(club=self.club)
        self.assertEqual(invitation.created_by, self.admin)
        self.assertAlmostEqual(
            (invitation.expires_at - timezone.now()).total_seconds(), 24 * 3600, delta=60,
        )
        page = self.client.get(reverse("club_members"))
        self.assertContains(page, f"/core/invite/{invitation.token}/")

    def test_members_cannot_create_invitations(self):
        self.client.login(username="viewer", password="pass-12345")
        self.client.post(reverse("create_invitation"))
        self.assertFalse(Invitation.objects.exists())

    def test_used_and_expired_invitations_are_not_listed(self):
        used = self.invite(used_at=timezone.now())
        expired = self.invite(expires_at=timezone.now() - datetime.timedelta(minutes=1))
        active = self.invite()
        self.client.login(username="capitan", password="pass-12345")
        tokens = [inv.token for inv, _ in self.client.get(reverse("club_members")).context["invitations"]]
        self.assertEqual(tokens, [active.token])
        self.assertNotIn(used.token, tokens)
        self.assertNotIn(expired.token, tokens)

    def test_revoke_is_scoped_to_the_admins_club(self):
        other_admin = User.objects.create_user("otro", password="pass-12345")
        create_club("Club B", "Madrid", other_admin)
        invitation = self.invite()
        self.client.login(username="otro", password="pass-12345")
        response = self.client.post(reverse("revoke_invitation", args=[invitation.public_id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Invitation.objects.filter(pk=invitation.pk).exists())

        self.client.login(username="capitan", password="pass-12345")
        self.client.post(reverse("revoke_invitation", args=[invitation.public_id]))
        self.assertFalse(Invitation.objects.filter(pk=invitation.pk).exists())

    def test_add_member_still_available_to_admins(self):
        self.client.login(username="capitan", password="pass-12345")
        self.client.post(reverse("club_members"), {
            "username": "manual", "password": "Clave-Segura-123", "email": "manual@example.com", "role": Membership.ADMIN,
        })
        self.assertTrue(Membership.objects.get(user__username="manual", club=self.club).is_admin)
        self.assertEqual(mail.outbox[-1].to, ["manual@example.com"])

    # --- Registro desde la invitación --------------------------------------

    def test_register_from_invitation_joins_club_as_member_and_sends_welcome(self):
        invitation = self.invite()
        self.assertContains(self.client.get(self.url(invitation)), "Únete a Club A")

        response = self.client.post(self.url(invitation), SIGNUP)
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

        user = User.objects.get(username="nuevo")
        membership = Membership.objects.get(user=user, club=self.club)
        self.assertEqual(membership.role, Membership.MEMBER)
        invitation.refresh_from_db()
        self.assertEqual(invitation.used_by, user)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["nuevo@example.com"])
        self.assertIn("Te has unido a Club A", email.subject)
        self.assertIn("Usuario: nuevo", email.body)
        self.assertIn("Administradores: capitan", email.body)
        html = email.alternatives[0][0]
        self.assertIn("capitan", html)
        self.assertIn("http://testserver/", html)

    def test_invitation_is_single_use(self):
        invitation = self.invite()
        self.client.post(self.url(invitation), SIGNUP)
        self.client.logout()
        response = self.client.post(self.url(invitation), {**SIGNUP, "username": "segundo", "email": "s@example.com"})
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "ya se ha usado", status_code=410)
        self.assertFalse(User.objects.filter(username="segundo").exists())

    def test_expired_invitation_is_rejected(self):
        invitation = self.invite(expires_at=timezone.now() - datetime.timedelta(seconds=1))
        response = self.client.post(self.url(invitation), SIGNUP)
        self.assertContains(response, "ha caducado", status_code=410)
        self.assertFalse(User.objects.filter(username="nuevo").exists())

    def test_unknown_token_is_rejected(self):
        response = self.client.get(reverse("invitation", args=["no-existe"]))
        self.assertEqual(response.status_code, 410)

    def test_signup_requires_unique_email(self):
        invitation = self.invite()
        response = self.client.post(self.url(invitation), {**SIGNUP, "email": "CAPITAN@example.com"})
        self.assertContains(response, "Ya hay una cuenta con este email")
        self.assertFalse(User.objects.filter(username="nuevo").exists())
        invitation.refresh_from_db()
        self.assertFalse(invitation.is_used)

    def test_logged_in_user_joins_with_one_click(self):
        User.objects.create_user("jugador", password="pass-12345", email="j@example.com")
        invitation = self.invite()
        self.client.login(username="jugador", password="pass-12345")
        self.assertContains(self.client.get(self.url(invitation)), "Unirme como jugador")
        self.assertFalse(Membership.objects.filter(user__username="jugador").exists())

        self.client.post(self.url(invitation))
        self.assertTrue(Membership.objects.filter(user__username="jugador", club=self.club).exists())
        self.assertEqual(mail.outbox[0].to, ["j@example.com"])

    def test_existing_member_does_not_consume_invitation(self):
        invitation = self.invite()
        self.client.login(username="viewer", password="pass-12345")
        self.client.post(self.url(invitation))
        invitation.refresh_from_db()
        self.assertFalse(invitation.is_used)

    def test_returning_from_google_joins_automatically(self):
        invitation = self.invite()
        self.client.get(self.url(invitation))  # visitante anónimo abre el enlace
        google_user = User.objects.create_user("google", email="g@example.com")
        self.client.force_login(google_user)  # vuelve autenticado por Google
        response = self.client.get(self.url(invitation))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(Membership.objects.filter(user=google_user, club=self.club).exists())

    # --- Google -------------------------------------------------------------

    def test_google_button_hidden_without_credentials(self):
        invitation = self.invite()
        self.assertNotContains(self.client.get(self.url(invitation)), "Registrarme con Google")
        self.assertNotContains(self.client.get(reverse("login")), "Continuar con Google")

    @override_settings(**GOOGLE_ON)
    def test_google_button_shown_with_credentials(self):
        invitation = self.invite()
        page = self.client.get(self.url(invitation))
        self.assertContains(page, "Registrarme con Google")
        self.assertContains(page, "/accounts/google/login/")
        self.assertContains(self.client.get(reverse("login")), "Continuar con Google")
        self.assertContains(self.client.get(reverse("register_club")), "Crear mi cuenta con Google")

    @override_settings(**GOOGLE_ON)
    def test_google_login_redirects_to_google(self):
        response = self.client.post(reverse("google_login"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://accounts.google.com/"))

    def test_allauth_password_signup_is_closed(self):
        self.client.post(reverse("account_signup"), SIGNUP)
        self.assertFalse(User.objects.filter(username="nuevo").exists())


class LoginAndWelcomeTests(TestCase):
    def test_login_with_email(self):
        User.objects.create_user("capitan", password="pass-12345", email="capitan@example.com")
        response = self.client.post(reverse("login"), {"username": "capitan@example.com", "password": "pass-12345"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_club_sends_welcome_with_created_team(self):
        self.client.post(reverse("register_club"), {
            "name": "Nuevo Club", "location": "Cádiz", "gender": "M", "country": "ES", **SIGNUP,
        })
        self.assertTrue(Club.objects.filter(name="Nuevo Club").exists())
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("Has creado Nuevo Club", email.subject)
        self.assertIn("Equipo creado: Nuevo Club", email.body)
        self.assertIn("Administradores: nuevo", email.body)

    def test_welcome_is_skipped_without_email(self):
        user = User.objects.create_user("sinemail")
        club = create_club("Club", "X", user)
        self.assertFalse(send_welcome_email(user, club))
        self.assertEqual(mail.outbox, [])

    def test_welcome_failure_does_not_break_registration(self):
        with mock.patch("core.emails.ZyraEmail.send", side_effect=OSError("SMTP caído")):
            response = self.client.post(reverse("register_club"), {"name": "Club X", "location": "Y", "gender": "F", "country": "PT", **SIGNUP})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Club.objects.filter(name="Club X").exists())

    def test_corporate_footer_with_inline_logo(self):
        user = User.objects.create_user("u", email="u@example.com")
        send_welcome_email(user, create_club("Club", "X", user))
        email = mail.outbox[0]
        self.assertIn("Contacto: join.zyra@gmail.com", email.body)
        self.assertIn(f"cid:{LOGO_CID}", email.alternatives[0][0])
        self.assertIn("mailto:join.zyra@gmail.com", email.alternatives[0][0])

        mime = email.message()
        related = next(p for p in mime.walk() if p.get_content_type() == "multipart/related")
        logo = next(p for p in related.walk() if p.get_content_type() == "image/png")
        self.assertEqual(logo["Content-ID"], f"<{LOGO_CID}>")


@override_settings(**GOOGLE_ON)
class GoogleSameAccountTests(TestCase):
    """Entrar con Google usa la cuenta existente con el mismo email."""

    def setUp(self):
        self.admin = User.objects.create_user("capitan", password="pass-12345", email="Capitan@Example.com")
        self.club = create_club("Club A", "Sevilla", self.admin)

    def google_login(self, email, verified=True, sub="google-123"):
        from allauth.core import context
        from allauth.socialaccount.adapter import get_adapter
        from allauth.socialaccount.helpers import complete_social_login
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        request = RequestFactory().get("/accounts/google/login/callback/")
        request.session = SessionStore()
        request.user = AnonymousUser()
        request._messages = FallbackStorage(request)
        provider = get_adapter(request).get_provider(request, "google")
        sociallogin = provider.sociallogin_from_response(request, {
            "sub": sub, "email": email, "email_verified": verified, "name": "Capitán",
        })
        with context.request_context(request):
            complete_social_login(request, sociallogin)
        return request

    def test_google_login_uses_existing_account_and_keeps_password(self):
        request = self.google_login("capitan@example.com")
        self.assertEqual(request.user, self.admin)
        self.assertEqual(User.objects.count(), 1)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.has_usable_password())
        self.assertTrue(self.admin.socialaccount_set.filter(provider="google").exists())
        # Sigue pudiendo entrar con usuario y contraseña
        self.assertTrue(self.client.login(username="capitan", password="pass-12345"))

    def test_second_google_login_goes_to_same_account(self):
        self.google_login("capitan@example.com")
        request = self.google_login("capitan@example.com")
        self.assertEqual(request.user, self.admin)
        self.assertEqual(User.objects.count(), 1)

    def test_unverified_google_email_does_not_take_over_account(self):
        request = self.google_login("capitan@example.com", verified=False, sub="otro")
        self.assertNotEqual(request.user, self.admin)

    def test_new_email_creates_new_account_without_club(self):
        request = self.google_login("nuevo@example.com", sub="nuevo")
        self.assertNotEqual(request.user, self.admin)
        self.assertEqual(request.user.email, "nuevo@example.com")
        self.assertFalse(Membership.objects.filter(user=request.user).exists())
