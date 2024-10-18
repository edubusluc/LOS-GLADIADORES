from django.db import models
from call.models import Call
from players.models import Player

# Create your models here.
class CallLog (models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='logs')
    text = models.TextField()