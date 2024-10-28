import json
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "snp_gladiadores.settings")
django.setup()

from players.models import Player
from match.models import Match, Game, Result
from call.models import Call
from team.models import Team
from datetime import datetime
from penalty.models import Penalty
from callLog.models import CallLog


def truncate_all_tables():
    
    models_to_truncate = [
        Player,
        Team,
        Match,
        Call,
        Game, 
        Result,
        Penalty,
        CallLog
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
                last_name = m['last_name'],
                position = m['position'],
                skillfull_hand = m['skillfull_hand'],
                team = team
            )

def create_match():
    with open('populate/match.json', 'r', encoding='utf-8') as file:
        messages_content = json.load(file)
        matches_to_create = []
        for match_data in messages_content:
            try:
                local_team = Team.objects.get(name=match_data["local"])
                visitor_team = Team.objects.get(name=match_data["visiting"])
            except Team.DoesNotExist as e:
                print(f"Error: {e}")
                continue

            start_date = datetime.strptime(match_data['start_date'], '%Y-%m-%d').date()

            Match.objects.create(
                local = local_team,
                visiting = visitor_team,
                start_date = start_date,
                draft_mode = match_data['draft_mode'],
                season = match_data['season'],
                result_points = match_data['result_points'],
                result = match_data['result']
            )


def create_call():
    with open('populate/call.json', 'r', encoding='utf-8') as file:
        calls_content = json.load(file)
        for c in calls_content:
            match_criteria = c["match_criteria"]
            players = c["players"]
            players_list = []  # Reiniciar para cada partido

            try:
                match = Match.objects.get(
                    local=Team.objects.get(name=match_criteria["local_team"]),
                    visiting=Team.objects.get(name=match_criteria["visitor_team"])
                )
            except Match.DoesNotExist:
                print(f"No se encontró el partido con los criterios: {match_criteria}")
                continue

            call = Call.objects.create(
                match=match,
                draft_mode=c['draft_mode']
            )

            for player in players:
                name = player['name']
                last_name = player['last_name']
                try:
                    player_instance = Player.objects.get(
                        name=name,
                        last_name=last_name
                    )
                    players_list.append(player_instance)  # Agregar a la lista de jugadores
                except Player.DoesNotExist:
                    print(f"No se encontró el jugador: {name} {last_name}")

            call.players.set(players_list)


def create_team():
    with open('populate/teams.json', 'r', encoding='utf-8') as file:
        messages_content = json.load(file)
        for m in messages_content:
            Team.objects.create(
                name = m['name'],
                in_group = m['in_group'],
                location = m['location'],
                photo = m['photo']
            )

def create_games():
    with open('populate/games.json', 'r', encoding='utf-8') as file:
        games_content = json.load(file)
        for g in games_content:
            match_criteria = g["match_criteria"]
            matches = g["matches"]
            try:
                match = Match.objects.get(
                    local=Team.objects.get(name = match_criteria["local_team"]),
                    visiting=Team.objects.get(name = match_criteria["visitor_team"])
                )
            except Match.DoesNotExist:
                print(f"No se encontró el partido con los criterios: {match_criteria}")
                continue

            for m in matches:
                game = Game.objects.create(
                    match = match,
                    n_game = m["n_game"],
                    player_1_visiting = Player.objects.get(
                        name=m["player_1_visiting"]["name"], 
                        last_name=m["player_1_visiting"]["last_name"]
                    ),

                    player_2_visiting = Player.objects.get(
                        name=m["player_2_visiting"]["name"], 
                        last_name=m["player_2_visiting"]["last_name"]
                    ),

                    score =m["score"],
                    winner =m["winner"],
                    draft_mode = m["draft_mode"]
            )
                game.save()

def create_result():
    with open('populate/results.json', 'r', encoding='utf-8') as file:
        result_content = json.load(file)
        for g in result_content:        
            game_criteria = g["game_criteria"]
            results = g["results"]
            try:
                game = Game.objects.get(
                    player_1_visiting = Player.objects.get(
                        name=game_criteria["player_1_visiting"]["name"], 
                        last_name=game_criteria["player_1_visiting"]["last_name"]
                    ),

                    player_2_visiting = Player.objects.get(
                        name=game_criteria["player_2_visiting"]["name"], 
                        last_name=game_criteria["player_2_visiting"]["last_name"]
                    ))
            except Match.DoesNotExist:
                print(f"No se encontró un Game: {game_criteria} con los criterios establecidos")
                continue

            for r in results:
                result = Result.objects.create(
                    game = game,
                    set1_local = r["set1_local"],
                    set1_visiting =  r["set1_visiting"],
                    set2_local = r["set2_local"],
                    set2_visiting = r["set2_visiting"],
                    set3_local = r["set3_local"],
                    set3_visiting = r["set3_visiting"],
                    result = r["result"],
                    draft_mode = False
                )
                result.save()

def populate_database():
    create_team()
    create_players()
    create_match()
    create_call()
    create_games()
    create_result()
    

if __name__ == "__main__":
    truncate_all_tables()
    populate_database()
    print("Database successfully populated.")
