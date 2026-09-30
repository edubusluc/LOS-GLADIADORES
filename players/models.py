import datetime

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from core import crypto
from core.models import Club
from team.models import Team

# Mes en el que empieza la temporada (9 = septiembre).
# Con esto, entre septiembre de 2026 y agosto de 2027 la temporada actual es "2026-2027".
SEASON_START_MONTH = 9


def current_season():
    """Temporada actual ("2026-2027"). Función a nivel de módulo: las migraciones la referencian."""
    today = datetime.date.today()
    start = today.year if today.month >= SEASON_START_MONTH else today.year - 1
    return f"{start}-{start + 1}"


class Player(models.Model):
    POSITIONS = [
        ("Derecha", "Derecha"),
        ("Revés", "Revés"),
        ("Mixto", " Mixto"),
        ("NONE", "NONE"),
    ]
    HAND = [
        ("Diestro", "Diestro"),
        ("Zurdo", "Zurdo"),
        ("NONE", "NONE")
    ]
    name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    position = models.CharField(max_length=10, choices=POSITIONS, default="NONE")
    skillfull_hand = models.CharField(max_length=10, choices=HAND, default="NONE")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="players", null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team")
    photo = models.ImageField(upload_to='static/profile', null=True, blank=True)
    snp_score = models.FloatField(null=True)
    in_team = models.BooleanField(default=True)
    joined_season = models.CharField(
        "Temporada en la que se unió",
        max_length=9,
        default=current_season,
        validators=[RegexValidator(r'^\d{4}-\d{4}$', 'Usa el formato 2024-2025.')],
        help_text="Formato 2024-2025. Se usa para contar a cuántas convocatorias no se ha apuntado.",
    )

    def save(self, *args, **kwargs):
        # Los jugadores siempre pertenecen al equipo propio de su club.
        if self.club_id and not self.team_id:
            self.team = self.club.own_team
        super().save(*args, **kwargs)

    def __str__(self):
        return str(f'{self.name} {self.last_name}')

    def get_first_last_name(self):
        return self.last_name.split()[0]  # Obtiene el primer apellido

class SnpAccount(models.Model):
    """
    Cuenta de SNP (snpgalaxy.com) del capitán de un club, con la que el proceso
    ``update_snp_scores`` descarga cada semana los puntos SNP de sus jugadores.
    Usuario y contraseña se guardan cifrados (core/crypto.py).
    """
    club = models.OneToOneField(Club, on_delete=models.CASCADE, related_name="snp_account")
    username_encrypted = models.TextField()
    password_encrypted = models.TextField()
    # Número del equipo en SNP (4380 en .../equipo/view/4380). Vacío: el único equipo de la cuenta.
    team_id = models.CharField("Equipo en SNP", max_length=20, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_ok = models.BooleanField(null=True)
    last_sync_message = models.TextField(blank=True)

    @property
    def username(self):
        return crypto.decrypt(self.username_encrypted)

    @username.setter
    def username(self, value):
        self.username_encrypted = crypto.encrypt(value)

    @property
    def password(self):
        return crypto.decrypt(self.password_encrypted)

    @password.setter
    def password(self, value):
        self.password_encrypted = crypto.encrypt(value)

    def __str__(self):
        return f"Cuenta SNP de {self.club}"
