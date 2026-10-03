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
    # Club suspendido por el personal de Zyra (back-office): sus miembros no pueden entrar
    # hasta que se reactive. No se borra nada.
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.CharField(max_length=500, blank=True)

    @property
    def is_suspended(self):
        return self.suspended_at is not None

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
    Enlace de un solo uso que un capitán envía por email para que un jugador se
    registre (o, si ya tiene cuenta, se una) al club como miembro. Caduca a las 24 h.
    """
    PUBLIC_ID_PREFIX = "INV"
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invitations")
    token = models.CharField(max_length=64, unique=True, default=_invitation_token, editable=False)
    # Email al que se envió. Vacío en las invitaciones antiguas, que se compartían como enlace.
    email = models.EmailField(blank=True)
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


class PhotoCheck(PublicIdModel):
    """
    Resultado de validar una foto subida (escudo o foto de jugador) con AWS Rekognition
    (core/moderation.py). Las rechazadas no se guardan; las que no se han podido validar
    (sin configurar, fuera del plan gratuito, error) se guardan y el personal las revisa
    en el back-office.
    """
    PUBLIC_ID_PREFIX = "PHC"
    APPROVED = "approved"
    REJECTED = "rejected"
    UNCHECKED = "unchecked"
    REVIEWED = "reviewed"
    STATUSES = [
        (APPROVED, _("Validada")),
        (REJECTED, _("Rechazada")),
        (UNCHECKED, _("Pendiente de revisar")),
        (REVIEWED, _("Revisada por el personal")),
    ]

    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_checks")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_checks",
    )
    team = models.ForeignKey("team.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_checks")
    player = models.ForeignKey("players.Player", on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_checks")
    # Ruta en el almacenamiento (vacía en las rechazadas, que no se guardan).
    photo = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES)
    # Motivo: etiquetas de Rekognition que la rechazaron o por qué no se validó.
    reason = models.CharField(max_length=500, blank=True)
    # True si se llamó a Rekognition (cuenta para el límite mensual gratuito).
    api_called = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    @property
    def subject(self):
        return self.player or self.team

    @property
    def subject_label(self):
        from django.utils.translation import gettext

        if self.player:
            return gettext("Foto de %(player)s") % {"player": self.player.full_name}
        if self.team:
            return gettext("Escudo de %(team)s") % {"team": self.team.name}
        return gettext("Foto")

    @property
    def owner(self):
        """A quién se avisa si se elimina: el jugador enlazado o, si no, quien la subió."""
        return (self.player.user if self.player and self.player.user else None) or self.uploaded_by

    @property
    def in_use(self):
        """La foto sigue siendo la del equipo o jugador."""
        subject = self.subject
        return bool(self.photo and subject and subject.photo and subject.photo.name == self.photo)

    def __str__(self):
        return f"{self.get_status_display()}: {self.photo or '—'}"


class PhotoRemoval(PublicIdModel):
    """
    Foto eliminada por el personal desde el back-office por no cumplir los términos y
    condiciones. Se avisa por email al jugador (o a quien subió el escudo); las veces
    que le ha pasado a un usuario se muestran al personal, que puede suspender su cuenta
    y eliminar el equipo si se repite.
    """
    PUBLIC_ID_PREFIX = "PHR"
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_removals",
    )
    club = models.ForeignKey(Club, on_delete=models.SET_NULL, null=True, blank=True, related_name="photo_removals")
    # De quién era la foto: «Jugador ANA RUIZ» o «Escudo de CD Tomares».
    subject = models.CharField(max_length=200)
    reason = models.CharField(max_length=500, blank=True)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} ({self.created_at:%d/%m/%Y})"
