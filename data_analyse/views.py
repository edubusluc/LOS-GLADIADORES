from django.shortcuts import render
from match.models import Match, Game
from players.models import Player
from team.models import Team
from django.db.models import Q
from call.models import Call
from django.views.decorators.http import require_GET
import json

#ESTADISTICAS EQUIPO
LOCAL_WIN = "Victoria Local"
VISITING_WIN = "Victoria Visitante"

def get_current_season(request):
    return request.GET.get('season')

def get_total_season(matchs):
    seasons = set()
    for m in matchs:
        seasons.add(m.season)
    return seasons

def get_team():
    team = Team.objects.filter(name="LOS GLADIADORES").first()
    return team if team else None

def calculate_match_statistics(season, team):
    if season is None:
        total_matches = Match.objects.filter(draft_mode=False).count()
        won_local = Match.objects.filter(local=team, result=LOCAL_WIN, draft_mode=False).count()
        won_visiting = Match.objects.filter(visiting=team, result=VISITING_WIN, draft_mode=False).count()
    else:
        total_matches = Match.objects.filter(season=season, draft_mode=False).count()
        won_local = Match.objects.filter(season=season, local=team, result=LOCAL_WIN, draft_mode=False).count()
        won_visiting = Match.objects.filter(season=season, visiting=team, result=VISITING_WIN, draft_mode=False).count()

    total_won = won_local + won_visiting
    lost_matches = total_matches - total_won
    percentage_won = round((total_won / total_matches) * 100, 2) if total_matches > 0 else 0
    percentage_lost = round((lost_matches / total_matches) * 100, 2) if total_matches > 0 else 0

    return total_matches, total_won, lost_matches, percentage_won, percentage_lost

def calculate_local_game_statistics(season, team):
    if season is None:
        match_local = Match.objects.filter(local=team, draft_mode=False)
    else:
        match_local = Match.objects.filter(season=season, local=team, draft_mode=False)

    local_games_won, local_games_lost = 0, 0

    for m in match_local:
        for g in m.games.all():
            result = g.results.first()
            local_games_won += result.set1_local + result.set2_local + (result.set3_local or 0)
            local_games_lost += result.set1_visiting + result.set2_visiting + (result.set3_visiting or 0)

    total_local_games = local_games_won + local_games_lost
    percentage_local_games_won = round((local_games_won / total_local_games * 100), 2) if total_local_games > 0 else 0
    percentage_local_games_lost = round((local_games_lost / total_local_games * 100), 2) if total_local_games > 0 else 0

    return local_games_won, local_games_lost, percentage_local_games_won, percentage_local_games_lost

def calculate_visiting_game_statistics(season, team):
    if season is None:
        match_visiting = Match.objects.filter(visiting=team, draft_mode=False)
    else:
        match_visiting = Match.objects.filter(season=season, visiting=team, draft_mode=False)

    visiting_games_won, visiting_games_lost = 0, 0

    for m in match_visiting:
        for g in m.games.all():
            result = g.results.first()
            visiting_games_won += result.set1_visiting + result.set2_visiting + (result.set3_visiting or 0)
            visiting_games_lost += result.set1_local + result.set2_local + (result.set3_local or 0)

    total_visiting_games = visiting_games_won + visiting_games_lost
    percentage_visiting_games_won = round((visiting_games_won / total_visiting_games * 100), 2) if total_visiting_games > 0 else 0
    percentage_visiting_games_lost = round((visiting_games_lost / total_visiting_games * 100), 2) if total_visiting_games > 0 else 0

    return visiting_games_won, visiting_games_lost, percentage_visiting_games_won, percentage_visiting_games_lost

def calculate_matches_won_per_year(team):
    dicc_match = {}
    year = set()
    
    # Filtra partidos que no están en modo draft
    all_matchs = Match.objects.filter(draft_mode=False)

    # Agrega las temporadas al conjunto
    for m in all_matchs:
        year.add(m.season)

    # Recorre cada año en el conjunto
    for y in year:    
        if y not in dicc_match:
            dicc_match[y] = {'won': 0, 'lost': 0}  # Inicializa contadores para ganados y perdidos

        # Contar partidos ganados como local
        match_won_local = Match.objects.filter(season=y, local=team, result="Victoria Local", draft_mode=False).count()
        # Contar partidos perdidos como local
        match_lost_local = Match.objects.filter(season=y, local=team, result="Victoria Visitante", draft_mode=False).count()
        
        # Contar partidos ganados como visitante
        match_won_visiting = Match.objects.filter(season=y, visiting=team, result="Victoria Visitante", draft_mode=False).count()
        # Contar partidos perdidos como visitante
        match_lost_visiting = Match.objects.filter(season=y, visiting=team, result="Victoria Local", draft_mode=False).count()

        # Suma los partidos ganados
        dicc_match[y]['won'] += match_won_local + match_won_visiting
        
        # Suma los partidos perdidos
        dicc_match[y]['lost'] += match_lost_local + match_lost_visiting
        dicc_match = dict(sorted(dicc_match.items()))

    return dicc_match
def count_games(player, role, winner, n_games, season):
    """Helper function to count games for a player."""
    filter_conditions = Q(**{f'player_1_{role}': player.id}) | Q(**{f'player_2_{role}': player.id})
    filter_conditions &= Q(winner=winner, draft_mode=False, n_game__in=n_games)
    
    if season:  # Solo aplica el filtro de temporada si `season` tiene un valor
        filter_conditions &= Q(match__season=season)

    return Game.objects.filter(filter_conditions).count()

def column_chart(season):
    players = Player.objects.all()
    dicc = {
        p: {
            'Partidos de 2 puntos ganados': 0,
            'Partidos de 2 puntos perdidos': 0,
            'Partidos de 3 puntos ganados': 0,
            'Partidos de 3 puntos perdidos': 0,
        } for p in players
    }

    for player in players:
        # Partidos locales
        dicc[player]['Partidos de 3 puntos ganados'] += count_games(player, 'local', "Local", [1, 2],season)
        dicc[player]['Partidos de 3 puntos perdidos'] += count_games(player, 'local', "Visitante", [1, 2],season)
        dicc[player]['Partidos de 2 puntos ganados'] += count_games(player, 'local', "Local", [3, 4, 5],season)
        dicc[player]['Partidos de 2 puntos perdidos'] += count_games(player, 'local', "Visitante", [3, 4, 5],season)

        # Partidos visitantes
        dicc[player]['Partidos de 3 puntos ganados'] += count_games(player, 'visiting', "Visitante", [1, 2],season)
        dicc[player]['Partidos de 3 puntos perdidos'] += count_games(player, 'visiting', "Local", [1, 2],season)
        dicc[player]['Partidos de 2 puntos ganados'] += count_games(player, 'visiting', "Visitante", [3, 4, 5],season)
        dicc[player]['Partidos de 2 puntos perdidos'] += count_games(player, 'visiting', "Local", [3, 4, 5],season)


    return dicc  # No olvides devolver el diccionario resultante

def format_for_chart(dic):
    players = []
    for player, stats in dic.items():
        players.append({
            'player': str(player), 
            'data': [
                stats['Partidos de 2 puntos ganados'],
                stats['Partidos de 2 puntos perdidos'],
                stats['Partidos de 3 puntos ganados'],
                stats['Partidos de 3 puntos perdidos'],
            ]
        })
    return players

@require_GET
def team_statistics(request):
    seasons = get_total_season(Match.objects.all())
    selected_season = request.GET.get("season")
    team = get_team()

    dicc = column_chart(selected_season)
    column_chart_data = format_for_chart(dicc)

    if not team:
        return render(request, 'team_statistics.html', {"seasons": seasons})

    # Se pasa None si no hay season seleccionada
    total_matches, total_won, lost_matches, percentage_won, percentage_lost = calculate_match_statistics(selected_season or None, team)
    local_games_won, local_games_lost, percentage_local_games_won, percentage_local_games_lost = calculate_local_game_statistics(selected_season or None, team)
    visiting_games_won, visiting_games_lost, percentage_visiting_games_won, percentage_visiting_games_lost = calculate_visiting_game_statistics(selected_season or None, team)
    
    #LINE CHART
    dicc_line_chart = calculate_matches_won_per_year(team)
    print(dicc_line_chart)


    context = {
        'team': team,
        'total_matches': total_matches,
        'won_matches': total_won,
        'lost_matches': lost_matches,
        'local_games_won': local_games_won,
        'local_games_lost': local_games_lost,
        'percentage_won': percentage_won,
        'percentage_lost': percentage_lost,
        'visiting_games_won': visiting_games_won,
        'visiting_games_lost': visiting_games_lost,
        'percentage_local_games_won': percentage_local_games_won,
        'percentage_local_games_lost': percentage_local_games_lost,
        'percentage_visiting_games_won': percentage_visiting_games_won,
        'percentage_visiting_games_lost': percentage_visiting_games_lost,
        'dicc_line_chart':dicc_line_chart,
        "seasons": seasons,
        "selected_season": selected_season,
        "column_chart_data": column_chart_data
    }

    return render(request, 'team_statistics.html', context)





# ESTADIISTICAS JUGADORES:
def get_player_statistics(player, season):
    # Obtener estadísticas del jugador
    stats = {
        'won_games_local': 0,
        'lost_games_local': 0,
        'won_games_visiting': 0,
        'lost_games_visiting': 0,
        'total_match': 0,
        'present_call': 0,
        'total_wins': 0,
        'total_lost': 0,
        'dicc_match': {},
    }

    # Contar partidos ganados/perdidos como local
    stats['won_games_local'] = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id),
        winner="Local",
        draft_mode=False,
        match__season=season
    ).count()

    stats['lost_games_local'] = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season=season
    ).count()

    # Contar partidos ganados/perdidos como visitante
    stats['won_games_visiting'] = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season=season
    ).count()

    stats['lost_games_visiting'] = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Local",
        draft_mode=False,
        match__season=season
    ).count()

    # Total de partidos jugados
    stats['total_match'] = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id) | 
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        draft_mode=False,
        match__season=season
    ).count()

    return stats


def get_present_calls(player, current_season):
    """Contar las convocatorias presentes para la temporada actual."""
    return Call.objects.filter(
        draft_mode=False,
        players__id=player.id,
        match__season=current_season
    ).count()

def get_match_history(player, all_match):
    """Obtener historial de partidos por año."""
    dicc_match = {}
    for m in all_match:
        year = m.season

        if year not in dicc_match:
            dicc_match[year] = {'won': 0, 'lost': 0}

    won_games_local = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id),
        winner="Local",
        draft_mode=False,
        match__season = year
    ).count()


    won_games_visiting = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season = year
    ).count()

    lost_games_local = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season = year
    ).count()

    lost_games_visiting = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Local",
        draft_mode=False,
        match__season = year
    ).count()

    dicc_match[year]['won'] += (won_games_local + won_games_visiting)
    dicc_match[year]['lost'] += (lost_games_local + lost_games_visiting)

    return dicc_match



@require_GET
def statistics_per_player(request):
    all_match = Match.objects.all()
    players = Player.objects.all()
    seasons = get_total_season(all_match)

    player_id = request.GET.get('player')
    selected_season = request.GET.get('season')
    if player_id:
        player = Player.objects.get(id=player_id)
    else:
        return render(request, 'player_statistics.html', {"players": players, "seasons":seasons})

    stats = get_player_statistics(player, selected_season)
    current_season = get_current_season(request)
    stats['present_call'] = get_present_calls(player, current_season)

    # Historial de partidos
    dicc_match = get_match_history(player, all_match)
    years = sorted(dicc_match.keys())
    stats['games_won_per_year'] = [dicc_match[y]['won'] for y in years]
    stats['games_lost_per_year'] = [dicc_match[y]['lost'] for y in years]

    # Cálculos finales
    stats['total_wins'] = stats['won_games_local'] + stats['won_games_visiting']
    stats['total_lost'] = stats['lost_games_local'] + stats['lost_games_visiting']
    total_call = Call.objects.filter(draft_mode=False).count()
    stats['percentage_call'] = (stats['present_call'] / total_call) * 100 if total_call > 0 else 0
    stats['no_call'] = total_call - stats['present_call']

    # Serializa los datos de años y estadísticas a JSON
    stats['years'] = json.dumps(years)
    stats['games_won_per_year'] = json.dumps(stats['games_won_per_year'])
    stats['games_lost_per_year'] = json.dumps(stats['games_lost_per_year'])

    context = {
        "players": players,
        "selected_season": selected_season,
        "selected_player": player.id,
        **stats,
        "years": years,
        "seasons": seasons,
    }

    return render(request, 'player_statistics.html', context)

