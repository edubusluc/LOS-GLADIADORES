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

    def save(self, *args, **kwargs):
        self.clean()  # Llamar a la validación antes de guardar
        super().save(*args, **kwargs)

def validate_set_value(value):
    if value < 0 or value > 7:
        raise ValidationError('El valor debe estar entre 0 y 7.')
    
def validate_padle_score(s):
    valid_scores = [
        ('6', '0'), ('6', '1'), ('6', '2'), ('6', '3'), ('6', '4'), ('7', '5'),
        ('7', '6'), ('0', '6'), ('1', '6'), ('2', '6'), ('3', '6'), ('4', '6'), ('5', '7'), ('6', '7')
    ]
    if s not in valid_scores:
        raise ValidationError(f'El resultado {s} no es un resultado válido.')

def get_winner(score):
    local, visiting = score
    if int(local) > int(visiting):
        return 'local'  
    elif int(local) < int(visiting):
        return 'visiting' 
    else:
        return 'tie' 

def validate_result(set1, set2, set3):
    # Validar los sets 1 y 2
    validate_padle_score(set1)
    validate_padle_score(set2)

    # Obtener ganadores de los sets 1 y 2
    winner_set1 = get_winner(set1)
    winner_set2 = get_winner(set2)

    # Validar el set 3 solo si los ganadores de los sets 1 y 2 son diferentes
    if winner_set1 != winner_set2:
        validate_padle_score(set3)
    # Si los ganadores de set1 y set2 son idénticos, set3 debe ser 0-0
    
    elif set3 != ("0", "0"):
        raise ValidationError('El resultado no es válido.')


    
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
    def clean(self):
        validate_result(
            (self.set1_local, self.set1_visiting), 
            (self.set2_local, self.set2_visiting), 
            (self.set3_local, self.set3_visiting)
        )
        
    def save(self, *args, **kwargs):
        self.clean() 
        super().save(*args, **kwargs)
        






