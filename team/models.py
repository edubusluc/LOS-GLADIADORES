from django.db import models

# Create your models here.

class Team(models.Model):
    name = models.CharField(max_length=100, unique=True)
    in_group = models.BooleanField(default=False)
    location = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='static/team', null=True, blank=True)

    def __str__(self):
        return self.name

