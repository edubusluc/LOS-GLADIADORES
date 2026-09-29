from django import forms
from .models import Team

class Teamform (forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name','location', 'photo']

    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)

    def clean_name(self):
        # El nombre es único dentro de cada club (no globalmente).
        name = self.cleaned_data['name']
        duplicated = Team.objects.filter(club=self.club, name__iexact=name).exclude(pk=self.instance.pk)
        if duplicated.exists():
            raise forms.ValidationError("Ya existe un equipo con ese nombre en tu club.")
        return name
