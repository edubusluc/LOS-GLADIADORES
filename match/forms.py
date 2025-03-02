from django import forms
from .models import Match, Game, Result
from team.models import Team

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['local', 'visiting', 'start_date']
        widgets = {
            'local': forms.Select(),
            'visiting': forms.Select(),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super(MatchForm, self).__init__(*args, **kwargs)
        self.fields['local'].queryset = Team.objects.filter(in_group = True)
        self.fields['visiting'].queryset = Team.objects.filter(in_group = True)

class GameForm (forms.ModelForm):
    class Meta:
        model = Game
        fields= ['n_game', 'player_1_local', 'player_2_local', 'player_1_visiting', 'player_2_visiting']


class ResultForm(forms.ModelForm):
    class Meta:
        model = Result
        fields = ['result']