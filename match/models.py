from django.db import models
from players.models import Player
from django.core.exceptions import ValidationError
from datetime import datetime

# Create your models here.

from django.db import models
from team.models import Team

class Match(models.Model):
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
    
    def save(self, *args, **kwargs):
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Solo asigna una nueva temporada si es necesario
        if not self.season or self.season == "NONE":
            if current_month >= 9:  # Temporada empieza en septiembre
                self.season = f"{current_year}-{current_year + 1}"
            else:  # Temporada anterior
                self.season = f"{current_year - 1}-{current_year}"

        # Llama al método de guardado del padre
        super().save(*args, **kwargs)



class Game(models.Model):
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

def validate_set_value(value):
    if value < 0 or value > 7:
        raise ValidationError('El valor debe estar entre 0 y 7.')
    
class Result(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='results')
    result = models.CharField(max_length=100, null = True)
    set1_local = models.IntegerField(validators=[validate_set_value])
    set1_visiting = models.IntegerField(validators=[validate_set_value])
    set2_local = models.IntegerField(validators=[validate_set_value])
    set2_visiting = models.IntegerField(validators=[validate_set_value])
    set3_local = models.IntegerField(validators=[validate_set_value], null=True)
    set3_visiting = models.IntegerField(validators=[validate_set_value], null=True)
    draft_mode = models.BooleanField(default=True)


    def determine_winner(self):
        local_sets_won = 0
        visiting_sets_won = 0

        sets = [
            (self.set1_local, self.set1_visiting),
            (self.set2_local, self.set2_visiting),
            (self.set3_local, self.set3_visiting),
        ]

        for local_points, visiting_points in sets:
            if local_points > visiting_points:
                local_sets_won += 1
            elif visiting_points > local_points:
                visiting_sets_won += 1

        if local_sets_won > visiting_sets_won:
            return "Victoria Local"
        else:
            return "Victoria visitante"


