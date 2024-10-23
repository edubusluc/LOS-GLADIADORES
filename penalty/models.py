from django.db import models
from players.models import Player
from call.models import Call

# Create your models here.
class Penalty(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="player")
    reason = models.CharField(max_length=100)
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="call")
