"""Modelo del registro de cambios de una convocatoria."""
from django.db import models
from core.public_id import PublicIdModel
from call.models import Call
from players.models import Player

# Create your models here.
class CallLog(PublicIdModel):
    """Registro de lo que ha pasado en una convocatoria: líneas de texto separadas por «;»."""
    PUBLIC_ID_PREFIX = "LOG"
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='logs')
    text = models.TextField()