from django.db import models
from players.models import Player
from match.models import Match

# Create your models here.
class Call(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='match')
    players = models.ManyToManyField(Player, related_name='players')
    draft_mode = models.BooleanField(default=True)

    class Meta:
        unique_together = ('match',)
