from django import forms
from .models import Team

class Teamform (forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name','location', 'photo']