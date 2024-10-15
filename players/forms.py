from django import forms
from .models import Player

class Playerform (forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name','position', 'skillfull_hand']