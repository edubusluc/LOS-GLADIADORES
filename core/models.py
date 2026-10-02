import datetime
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .public_id import PublicIdModel


class Club(PublicIdModel):
    """
    Cada club es un "inquilino" de la aplicación: tiene sus propios jugadores,
    equipos rivales, partidos, convocatorias y estadísticas.
    Ningún usuario puede ver datos de un club al que no pertenece.
    """
    PUBLIC_ID_PREFIX = "CLB"
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "club"
            slug, n = base, 2
            while Club.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def own_team(self):
        """Equipo (Team) que representa al propio club en los enfrentamientos."""
        return self.teams.filter(is_own=True).first()

    def __str__(self):
        return self.name


class Membership(PublicIdModel):
    PUBLIC_ID_PREFIX = "MBR"
    ADMIN = "admin"
    MEMBER = "member"
    ROLES = [
        (ADMIN, _("Capitán")),
        (MEMBER, _("Miembro (solo lectura)")),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "club"], name="unique_membership_user_club"),
        ]

    @property
    def is_admin(self):
        return self.role == self.ADMIN

    def __str__(self):
        return f"{self.user} - {self.club} ({self.get_role_display()})"


INVITATION_TTL = datetime.timedelta(hours=24)


def _invitation_token():
    return secrets.token_urlsafe(24)


def _invitation_expiry():
    return timezone.now() + INVITATION_TTL


class Invitation(PublicIdModel):
    """
    Enlace de un solo uso que un capitán comparte para que un jugador se
    registre (o, si ya tiene cuenta, se una) al club como miembro. Caduca a las 24 h.
    """
    PUBLIC_ID_PREFIX = "INV"
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invitations")
    token = models.CharField(max_length=64, unique=True, default=_invitation_token, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="invitations_sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_invitation_expiry)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="invitations_used",
    )
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    def __str__(self):
        return f"Invitación a {self.club} ({self.token[:6]}…)"
