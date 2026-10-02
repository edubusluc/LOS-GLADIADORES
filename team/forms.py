from django import forms
from django.utils.translation import gettext as _
from .models import Team

class Teamform (forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'gender', 'country', 'location', 'photo']

    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)
        # Obligatorios en el formulario aunque los equipos antiguos los tengan vacíos.
        for name in ('gender', 'country'):
            self.fields[name].required = True
            self.fields[name].choices = [("", _("Elige una opción"))] + list(Team._meta.get_field(name).choices)

    def clean(self):
        # Mismo nombre, categoría y país en el club: es el mismo equipo. Los nombres
        # parecidos solo se avisan (ver core/similarity.py).
        cleaned = super().clean()
        name, gender, country = cleaned.get('name'), cleaned.get('gender'), cleaned.get('country')
        if name and gender and country:
            duplicated = (Team.objects.filter(club=self.club, name__iexact=name, gender=gender, country=country)
                          .exclude(pk=self.instance.pk))
            if duplicated.exists():
                self.add_error('name', _("Ya existe un equipo con ese nombre, categoría y país en tu club."))
        return cleaned
