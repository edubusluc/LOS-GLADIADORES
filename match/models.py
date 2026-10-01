from django.db import models
from players.models import Player
from django.core.exceptions import ValidationError
from . import scoring
from datetime import datetime
from urllib.parse import quote

# Create your models here.

from django.db import models
from core.public_id import PublicIdModel
from core.models import Club
from team.models import Team

class Match(PublicIdModel):
    PUBLIC_ID_PREFIX = "MAT"
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name='matches', null=True)
    local = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='local_matches', null=True)
    visiting = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='visiting_matches', null=True)
    
    
    POSSIBLE_RESULT = [
        ("Victoria Local", "Victoria Local"),
        ("Victoria Visitante", "Victoria Visitante"),
        ("EMPATE", "Empate"),
        ("NONE", "Ninguno"),
    ]
    
    start_date = models.DateField()
    result = models.CharField(max_length=20, choices=POSSIBLE_RESULT, blank = True, default="NONE")
    result_points = models.CharField(max_length=20, blank = True, default="NONE")
    draft_mode = models.BooleanField(default=True)
    season = models.CharField(max_length=9, blank = True, default="NONE")
    # Copia de la ubicación del equipo local al crear el partido. Es una copia, no un
    # enlace: si el equipo cambia de sede después, los partidos ya creados no cambian.
    location = models.CharField(max_length=100, blank=True, default="")
    
    class Meta:
        indexes = [
            models.Index(fields=["club", "season", "start_date"], name="match_club_season_idx"),
        ]

    def save(self, *args, **kwargs):
        # Asignar la temporada según la fecha de inicio
        if not self.season or self.season == "NONE":
            if self.start_date:
                if self.start_date.month >= 9:  # Septiembre o después
                    self.season = f"{self.start_date.year}-{self.start_date.year + 1}"
                else:  # Antes de septiembre (enero a agosto)
                    self.season = f"{self.start_date.year - 1}-{self.start_date.year}"

        if not self.location and self.local_id:
            self.location = self.local.location

        # Llama al método de guardado del padre
        super().save(*args, **kwargs)
    
    @property
    def maps_url(self):
        """Enlace de Google Maps a la ubicación del partido; '' si no tiene."""
        if not self.location:
            return ""
        return "https://www.google.com/maps/search/?api=1&query=" + quote(self.location)

    @property
    def own_is_local(self):
        return bool(self.local and self.local.is_own)

    @property
    def own_is_visiting(self):
        return bool(self.visiting and self.visiting.is_own)

    def __str__(self):
        return f'{self.local} - {self.visiting}'



class Game(PublicIdModel):
    PUBLIC_ID_PREFIX = "GAM"
    NUMBER_GAME = [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
    ]

    WINNER = [
        ("Local", "Local"),
        ("Visitante", "Visitante"),
    ]

    SCORE = [
        ("3","3"),
        ("2","2"),
    ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='games')
    n_game = models.IntegerField(choices= NUMBER_GAME, null = True)
    player_1_local = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player_1_local', null=True)
    player_2_local = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player_2_local', null=True)
    player_1_visiting = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player_1_visiting', null=True)
    player_2_visiting = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player_2_visiting', null=True)
    score = models.IntegerField(choices= NUMBER_GAME, null = True)
    winner = models.CharField(max_length=10, null=True)
    draft_mode = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Cada enfrentamiento tiene como mucho un partido 1, un partido 2... (evita duplicados)
            models.UniqueConstraint(fields=["match", "n_game"], name="unique_game_number_per_match"),
            models.CheckConstraint(check=models.Q(n_game__gte=1, n_game__lte=5) | models.Q(n_game__isnull=True),
                                   name="game_number_between_1_and_5"),
        ]

    def save(self, *args, **kwargs):
        self.clean()  # Llamar a la validación antes de guardar
        super().save(*args, **kwargs)


    def __str__(self):
        if self.player_1_local:
            return f'{self.match}-{self.n_game}: {self.player_1_local} - {self.player_2_local}'
        else:
            return f'{self.player_1_visiting} - {self.player_2_visiting}'


def validate_set_value(value):
    # Límite amplio para admitir un super tie-break en el tercer set; las reglas
    # completas de pádel están en match/scoring.py (Result.clean).
    if value < 0 or value > 30:
        raise ValidationError('El valor debe estar entre 0 y 30.')


class Result(PublicIdModel):
    PUBLIC_ID_PREFIX = "RES"
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='results')
    result = models.CharField(max_length=100, null = True)
    set1_local = models.IntegerField(validators=[validate_set_value])
    set1_visiting = models.IntegerField(validators=[validate_set_value])
    set2_local = models.IntegerField(validators=[validate_set_value])
    set2_visiting = models.IntegerField(validators=[validate_set_value])
    set3_local = models.IntegerField(validators=[validate_set_value], null=True)
    set3_visiting = models.IntegerField(validators=[validate_set_value], null=True)
    draft_mode = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # Un solo resultado por partido
            models.UniqueConstraint(fields=["game"], name="unique_result_per_game"),
        ]

    def sets(self):
        return [
            (self.set1_local, self.set1_visiting),
            (self.set2_local, self.set2_visiting),
            (self.set3_local, self.set3_visiting),
        ]

    def clean(self):
        """Valida el resultado con las reglas del pádel y normaliza el set 3 no jugado."""
        values = [scoring.to_int(v) for pair in self.sets() for v in pair]
        sets, self._winner = scoring.validate_padel_result(
            (values[0], values[1]), (values[2], values[3]), (values[4], values[5])
        )
        (self.set1_local, self.set1_visiting), (self.set2_local, self.set2_visiting), \
            (self.set3_local, self.set3_visiting) = sets

    def determine_winner(self):
        winner = getattr(self, "_winner", None)
        if winner is None:
            self.clean()
            winner = self._winner
        return "Victoria Local" if winner == "local" else "Victoria Visitante"

    def save(self, *args, **kwargs):
        self.clean() 
        super().save(*args, **kwargs)
        






