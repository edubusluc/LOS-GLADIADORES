import datetime

from django.core.validators import RegexValidator
from django.db import models
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
    score = models.IntegerField(default=5, null=True)
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