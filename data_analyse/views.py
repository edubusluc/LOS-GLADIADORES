from django.shortcuts import render
from match.models import Match, Game
from players.models import Player
from team.models import Team
from django.db.models import Q
from call.models import Call
from django.views.decorators.http import require_GET

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
    all_matchs = Match.objects.all()

    for m in all_matchs:
        year = m.season
        if year not in dicc_match:
            dicc_match[year] = {'won': 0}
        match_won_Local = Match.objects.filter(season=year, local=team, result=LOCAL_WIN, draft_mode=False).count()
        match_won_Visiting = Match.objects.filter(season=year, visiting=team, result=VISITING_WIN, draft_mode=False).count()
        dicc_match[year]['won'] += match_won_Local + match_won_Visiting

    years = sorted(dicc_match.keys())
    matches_won_per_year = [dicc_match[y]['won'] for y in years]
    return years, matches_won_per_year

@require_GET
def team_statistics(request):
    seasons = get_total_season(Match.objects.all())
    selected_season = request.GET.get("season")
    team = get_team()

    if not team:
        return render(request, 'team_statistics.html', {"seasons": seasons})

    # Se pasa None si no hay season seleccionada
    total_matches, total_won, lost_matches, percentage_won, percentage_lost = calculate_match_statistics(selected_season or None, team)
    local_games_won, local_games_lost, percentage_local_games_won, percentage_local_games_lost = calculate_local_game_statistics(selected_season or None, team)
    visiting_games_won, visiting_games_lost, percentage_visiting_games_won, percentage_visiting_games_lost = calculate_visiting_game_statistics(selected_season or None, team)
    years, matches_won_per_year = calculate_matches_won_per_year(team)

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
        'years': years,
        'matches_won_per_year': matches_won_per_year,
        "seasons": seasons,
        "selected_season": selected_season
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

    print("won-local",year, won_games_local)

    won_games_visiting = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season = year
    ).count()
    print("won-visiting",year, won_games_visiting)

    lost_games_local = Game.objects.filter(
        Q(player_1_local=player.id) | Q(player_2_local=player.id),
        winner="Visitante",
        draft_mode=False,
        match__season = year
    ).count()
    print("lost-local",year,lost_games_local)

    lost_games_visiting = Game.objects.filter(
        Q(player_1_visiting=player.id) | Q(player_2_visiting=player.id),
        winner="Local",
        draft_mode=False,
        match__season = year
    ).count()
    print("lost-visiting",year,lost_games_visiting)

    dicc_match[year]['won'] += (won_games_local + won_games_visiting)
    dicc_match[year]['lost'] += (lost_games_local + lost_games_visiting)

    return dicc_match

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

    context = {
        "players": players,
        "selected_season": selected_season,
        "selected_player": player.id,
        **stats,
        "years": years,
        "seasons": seasons,
    }

    return render(request, 'player_statistics.html', context)

