from django import forms
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from .models import Match, Game, Result
from team.models import Team

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['match_type', 'local', 'visiting', 'start_date']
        labels = {'local': _('Local'), 'visiting': _('Visitante'), 'start_date': _('Fecha')}
        widgets = {
            'match_type': forms.Select(),
            'local': forms.Select(),
            'visiting': forms.Select(),
            'start_date': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'data-datepicker': '', 'data-placeholder': _('Elige el día del partido')},
            ),
        }

    def __init__(self, *args, club=None, **kwargs):
        super(MatchForm, self).__init__(*args, **kwargs)
        self.club = club
        self.own_team = club.own_team if club else None
        # El equipo propio siempre se puede elegir, aunque no esté marcado "en el grupo".
        teams = Team.objects.filter(club=club).filter(Q(in_group=True) | Q(is_own=True)).order_by('-is_own', 'name')
        missing_team = _("Uno de los equipos no existe.")
        for name in ('local', 'visiting'):
            field = self.fields[name]
            field.queryset = teams
            field.required = True
            field.empty_label = _("Elige una opción")
            field.error_messages.update(required=_("Por favor, completa todos los campos."), invalid_choice=missing_team)
        if not self.is_bound and self.own_team and not self.initial.get('local') and not self.initial.get('visiting'):
            self.initial['local'] = self.own_team.pk
        # Si no se envía tipo, el partido es un enfrentamiento.
        self.fields['match_type'].required = False
        self.fields['match_type'].error_messages['invalid_choice'] = _("Tipo de partido no válido.")
        date_error = _("Fecha no válida. Usa el formato AAAA-MM-DD.")
        self.fields['start_date'].input_formats = ['%Y-%m-%d']
        self.fields['start_date'].error_messages.update(required=date_error, invalid=date_error)

    def clean_match_type(self):
        return self.cleaned_data.get('match_type') or Match.ENFRENTAMIENTO

    def clean(self):
        cleaned = super().clean()
        local, visiting = cleaned.get('local'), cleaned.get('visiting')
        if local and visiting:
            if local == visiting:
                raise forms.ValidationError(_("El equipo local y el visitante no pueden ser el mismo."))
            # El equipo del capitán (el equipo propio del club) tiene que jugar el partido.
            if self.own_team is None:
                raise forms.ValidationError(_("Tu club no tiene equipo propio: no se pueden crear partidos."))
            if self.own_team not in (local, visiting):
                raise forms.ValidationError(
                    _("Tu equipo (%(team)s) tiene que jugar el partido: elígelo como local o visitante.")
                    % {"team": self.own_team}
                )
        return cleaned

    def save(self, commit=True):
        match = super().save(commit=False)
        match.club = self.club
        if commit:
            match.save()
        return match

class GameForm (forms.ModelForm):
    class Meta:
        model = Game
        fields= ['n_game', 'player_1_local', 'player_2_local', 'player_1_visiting', 'player_2_visiting']


class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['result']