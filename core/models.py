from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Club(models.Model):
    """
    Cada club es un "inquilino" de la aplicación: tiene sus propios jugadores,
    equipos rivales, partidos, convocatorias y estadísticas.
    Ningún usuario puede ver datos de un club al que no pertenece.
    """
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


class Membership(models.Model):
    ADMIN = "admin"
    MEMBER = "member"
    ROLES = [
        (ADMIN, "Administrador"),
        (MEMBER, "Miembro (solo lectura)"),
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
