from django.db import models
from team.models import Team
#from core.models import CustomUser
# Create your models here.

class Player(models.Model):
    POSITIONS = [
        ("Derecha","Derecha"),
        ("Revés", "Revés"),
        ("Mixto"," Mixto"),
        ("NONE", "NONE"),
        ]
    HAND = [
        ("Diestro","Diestro"),
        ("Zurdo","Zurdo"),
        ("NONE","NONE")
        ]
    name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    position = models.CharField(max_length=10,choices= POSITIONS,default="NONE")
    skillfull_hand = models.CharField(max_length=10,choices=HAND,default="NONE")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team")
    photo = models.ImageField(upload_to='static/profile', null=True, blank=True)
    snp_score = models.FloatField(null=True)
    score = models.IntegerField(default=5, null = True)
    def __str__(self):
        return str(f'{self.name} {self.last_name}')
    

    def get_first_last_name(self):
         return self.last_name.split()[0]  # Obtiene el primer apellido


    
