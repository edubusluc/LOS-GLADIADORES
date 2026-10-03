from django import forms
from django.utils.translation import gettext as _
from core.images import clean_photo_field
from core.similarity import same_name
from core.validators import plain_text
from .models import Team

class Teamform (forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'gender', 'country', 'division', 'location', 'photo']

    def __init__(self, *args, club=None, **kwargs):
        self.club = club
        super().__init__(*args, **kwargs)
        plain_text(self, 'name', 'location')
        # Obligatorios en el formulario aunque los equipos antiguos los tengan vacíos.
        for name in ('gender', 'country', 'division'):
            self.fields[name].required = True
            self.fields[name].choices = [("", _("Elige una opción"))] + list(Team._meta.get_field(name).choices)

    def clean_photo(self):
        # Se valida, reduce y pasa a WebP antes de guardarla (core/images.py).
        return clean_photo_field(self)

    def clean(self):
        # No puede haber dos equipos del club con el mismo nombre (sin distinguir mayúsculas,
        # tildes ni signos) en la misma división. Los equipos antiguos sin división cuentan
        # para todas. Los nombres solo parecidos se avisan (ver core/similarity.py).
        cleaned = super().clean()
        name, division = cleaned.get('name'), cleaned.get('division')
        if name and division:
            others = Team.objects.filter(club=self.club, division__in=[division, ""]).exclude(pk=self.instance.pk)
            if any(same_name(name, t.name) for t in others):
                self.add_error('name', _("Ya existe un equipo con ese nombre en esa división en tu club."))
        return cleaned
