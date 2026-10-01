from django.db import models
from core.public_id import PublicIdModel
from players.models import Player
from call.models import Call

# Create your models here.
class Penalty(PublicIdModel):
    PUBLIC_ID_PREFIX = "PEN"
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="player")
    reason = models.CharField(max_length=100)
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="call")


    def __str__(self):
        return f"{self.player}  {self.reason}"
