from django.db import models
from core.public_id import PublicIdModel
from call.models import Call
from players.models import Player

# Create your models here.
class CallLog(PublicIdModel):
    PUBLIC_ID_PREFIX = "LOG"
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='logs')
    text = models.TextField()