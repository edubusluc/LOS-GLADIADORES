from django import forms
from .models import Player

class PlayerForm (forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'last_name', 'position', 'skillfull_hand', 'photo']