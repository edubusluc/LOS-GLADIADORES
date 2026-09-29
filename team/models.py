from django.db import models
from core.models import Club

# Create your models here.

class Team(models.Model):
    # null=True solo para poder migrar datos existentes (ver comando assign_default_club).
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="teams", null=True)
    # True para el equipo que representa al propio club; el resto son rivales.
    is_own = models.BooleanField(default=False)
    name = models.CharField(max_length=100)
    in_group = models.BooleanField(default=False)
    location = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='static/team', null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="unique_team_name_per_club"),
            models.UniqueConstraint(fields=["club"], condition=models.Q(is_own=True), name="unique_own_team_per_club"),
        ]

    def __str__(self):
        return self.name
