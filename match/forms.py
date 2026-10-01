from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Match, Game, Result
from team.models import Team

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['local', 'visiting', 'start_date']
        labels = {'local': _('Local'), 'visiting': _('Visitante'), 'start_date': _('Fecha')}
        widgets = {
            'local': forms.Select(),
            'visiting': forms.Select(),
            'start_date': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'data-datepicker': '', 'data-placeholder': _('Elige el día del partido')},
            ),
        }

    def __init__(self, *args, club=None, **kwargs):
        super(MatchForm, self).__init__(*args, **kwargs)
        teams = Team.objects.filter(club=club, in_group=True)
        self.fields['local'].queryset = teams
        self.fields['visiting'].queryset = teams

class GameForm (forms.ModelForm):
    class Meta:
        model = Game
        fields= ['n_game', 'player_1_local', 'player_2_local', 'player_1_visiting', 'player_2_visiting']


class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['result']