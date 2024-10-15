import json
from django.shortcuts import  get_object_or_404
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "snp_gladiadores.settings")
django.setup()

from players.models import Player
from match.models import Match
from call.models import Call
from team.models import Team

def truncate_all_tables():
    
    models_to_truncate = [
        Player
    ]
    for model1 in models_to_truncate:
        model1.objects.all().delete()
    print("All data has been deleted from the database.")

def create_players():
    with open('populate/players.json', 'r', encoding='utf-8') as file:
        messages_content = json.load(file)
        team, create = Team.objects.get_or_create(name="LOS GLADIADORES")
        for m in messages_content:
            Player.objects.create(
                name = m['name'],
                position = m['position'],
                skillfull_hand = m['skillfull_hand'],
                team = team
            )

def create_match():
    with open('populate/match.json', 'r', encoding='utf-8') as file:
        messages_content = json.load(file)
        local_team_name = "LA MAGIA DEL PADEL C"
        visiting_team_name = "LOS GLADIADORES"

        local_team, created = Team.objects.get_or_create(name=local_team_name)
        visiting_team, created = Team.objects.get_or_create(name=visiting_team_name)

        for m in messages_content:
            Match.objects.create(
                local = local_team,
                visiting = visiting_team,
                start_date = m['start_date'],
                draft_mode = m['draft_mode']
            )


def create_call():
    with open('populate/call.json', 'r', encoding='utf-8') as file:
        calls_content = json.load(file)
        for c in calls_content:
            # Obtener el partido correspondiente
            matches = Match.objects.all() 
            for m in matches:
                match_id = m.id

            match = get_object_or_404(Match, id=match_id)
            # Crear una instancia de Call
            call = Call.objects.create(
                match=match,
                draft_mode=c['draft_mode']
            )
            # Obtener jugadores y asociarlos
            players = Player.objects.filter(name__in=c['players'])
            call.players.set(players)  # Asocia los jugadores a la llamada


def create_team():
    with open('populate/teams.json', 'r', encoding='utf-8') as file:
        messages_content = json.load(file)
        for m in messages_content:
            Team.objects.create(
                name = m['name'],
            )



def populate_database():
    create_team()
    create_players()
    create_match()
    create_call()
    

if __name__ == "__main__":
    truncate_all_tables()
    populate_database()
    print("Database successfully populated.")
