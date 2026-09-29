from django.shortcuts import render
from match.models import Match, Game
from players.models import Player
from team.models import Team
from call.models import Call
from django.db.models import Q, Count
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404
from django.http import Http404
from core.decorators import club_required, club_admin_required
from penalty.models import Penalty
from players.models import current_season
from . import pairs as pair_stats

# ---------------------------------------------------------------
# ESTADÍSTICAS EQUIPO (sin cambios)
# ---------------------------------------------------------------
LOCAL_WIN = "Victoria Local"
VISITING_WIN = "Victoria Visitante"


def get_total_season(matchs):
    seasons = set()
    for m in matchs:
        seasons.add(m.season)
    return seasons


def calculate_match_statistics(season, team):
    if season is None:
        total_matches = Match.objects.filter(club=team.club, draft_mode=False).count()
        won_local = Match.objects.filter(local=team, result=LOCAL_WIN, draft_mode=False).count()
        won_visiting = Match.objects.filter(visiting=team, result=VISITING_WIN, draft_mode=False).count()
    else:
        total_matches = Match.objects.filter(club=team.club, season=season, draft_mode=False).count()
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
            if result is None:
                continue  # partido sin resultado registrado
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
            if result is None:
                continue  # partido sin resultado registrado
            visiting_games_won += result.set1_visiting + result.set2_visiting + (result.set3_visiting or 0)
            visiting_games_lost += result.set1_local + result.set2_local + (result.set3_local or 0)

    total_visiting_games = visiting_games_won + visiting_games_lost
    percentage_visiting_games_won = round((visiting_games_won / total_visiting_games * 100), 2) if total_visiting_games > 0 else 0
    percentage_visiting_games_lost = round((visiting_games_lost / total_visiting_games * 100), 2) if total_visiting_games > 0 else 0

    return visiting_games_won, visiting_games_lost, percentage_visiting_games_won, percentage_visiting_games_lost


def calculate_matches_won_per_year(team):
    dicc_match = {}
    year = set()

    all_matchs = Match.objects.filter(club=team.club, draft_mode=False)
    for m in all_matchs:
        year.add(m.season)

    for y in year:
        if y not in dicc_match:
            dicc_match[y] = {'won': 0, 'lost': 0}

        match_won_local = Match.objects.filter(season=y, local=team, result="Victoria Local", draft_mode=False).count()
        match_lost_local = Match.objects.filter(season=y, local=team, result="Victoria Visitante", draft_mode=False).count()
        match_won_visiting = Match.objects.filter(season=y, visiting=team, result="Victoria Visitante", draft_mode=False).count()
        match_lost_visiting = Match.objects.filter(season=y, visiting=team, result="Victoria Local", draft_mode=False).count()

        dicc_match[y]['won'] += match_won_local + match_won_visiting
        dicc_match[y]['lost'] += match_lost_local + match_lost_visiting
        dicc_match = dict(sorted(dicc_match.items()))

    return dicc_match


def count_games(player, role, winner, n_games, season):
    """Helper function to count games for a player."""
    filter_conditions = Q(**{f'player_1_{role}': player.id}) | Q(**{f'player_2_{role}': player.id})
    filter_conditions &= Q(winner=winner, draft_mode=False, n_game__in=n_games)

    if season:
        filter_conditions &= Q(match__season=season)

    return Game.objects.filter(filter_conditions).count()


def column_chart(club, season):
    # Solo los jugadores que siguen en el equipo
    players = Player.objects.filter(club=club, in_team=True)
    dicc = {
        f"{p.name} {p.last_name}": {
            'Partidos de 2 puntos ganados': 0,
            'Partidos de 2 puntos perdidos': 0,
            'Partidos de 3 puntos ganados': 0,
            'Partidos de 3 puntos perdidos': 0,
        } for p in players
    }

    for player in players:
        player_key = f"{player.name} {player.last_name}"
        # Partidos locales
        dicc[player_key]['Partidos de 3 puntos ganados'] += count_games(player, 'local', "Local", [1, 2], season)
        dicc[player_key]['Partidos de 3 puntos perdidos'] += count_games(player, 'local', "Visitante", [1, 2], season)
        dicc[player_key]['Partidos de 2 puntos ganados'] += count_games(player, 'local', "Local", [3, 4, 5], season)
        dicc[player_key]['Partidos de 2 puntos perdidos'] += count_games(player, 'local', "Visitante", [3, 4, 5], season)

        # Partidos visitantes
        dicc[player_key]['Partidos de 3 puntos ganados'] += count_games(player, 'visiting', "Visitante", [1, 2], season)
        dicc[player_key]['Partidos de 3 puntos perdidos'] += count_games(player, 'visiting', "Local", [1, 2], season)
        dicc[player_key]['Partidos de 2 puntos ganados'] += count_games(player, 'visiting', "Visitante", [3, 4, 5], season)
        dicc[player_key]['Partidos de 2 puntos perdidos'] += count_games(player, 'visiting', "Local", [3, 4, 5], season)

    return dicc


def format_for_chart(dic):
    players = []
    for player_name, stats in dic.items():
        players.append({
            'player': player_name,
            'data': [
                stats['Partidos de 2 puntos ganados'],
                stats['Partidos de 2 puntos perdidos'],
                stats['Partidos de 3 puntos ganados'],
                stats['Partidos de 3 puntos perdidos'],
            ]
        })
    return players


@club_required
@require_GET
def team_statistics(request):
    seasons = get_total_season(Match.objects.filter(club=request.club))
    selected_season = request.GET.get("season")
    team = request.club.own_team

    seasons = sorted(seasons, key=lambda s: int(s.split('-')[0]), reverse=True)

    dicc = column_chart(request.club, selected_season)
    column_chart_data = format_for_chart(dicc)

    if not team:
        return render(request, 'team_statistics.html', {"seasons": seasons})

    total_matches, total_won, lost_matches, percentage_won, percentage_lost = calculate_match_statistics(selected_season or None, team)
    local_games_won, local_games_lost, percentage_local_games_won, percentage_local_games_lost = calculate_local_game_statistics(selected_season or None, team)
    visiting_games_won, visiting_games_lost, percentage_visiting_games_won, percentage_visiting_games_lost = calculate_visiting_game_statistics(selected_season or None, team)

    dicc_line_chart = calculate_matches_won_per_year(team)

    # Top 5 (jugadores actuales del equipo), respetando la temporada elegida
    squad = list(Player.objects.filter(club=request.club, in_team=True))
    log = pair_stats.club_game_log(request.club, selected_season or None)

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
        'dicc_line_chart': dicc_line_chart,
        "seasons": seasons,
        "selected_season": selected_season,
        "column_chart_data": column_chart_data,
        "top_local_players": pair_stats.top_players(log, squad, local=True),
        "top_visiting_players": pair_stats.top_players(log, squad, local=False),
        "top_local_pairs": pair_stats.top_pairs(log, squad, local=True),
        "top_visiting_pairs": pair_stats.top_pairs(log, squad, local=False),
        "min_games_player": pair_stats.MIN_GAMES_PLAYER,
        "min_games_pair": pair_stats.MIN_GAMES_PAIR,
    }

    return render(request, 'team_statistics.html', context)


# ---------------------------------------------------------------
# ESTADÍSTICAS JUGADORES
# ---------------------------------------------------------------

# Orden cronológico de los partidos del jugador. De esto dependen las rachas.
# Si Match tiene un campo de fecha, cámbialo:
#   ORDER = ('match__date', 'match_id', 'n_game')
ORDER = ('match__season', 'match_id', 'n_game')

# Peso del "punto de partida" neutro (50 %) en la afinidad, medido en puntos en juego.
PRIOR_POINTS = 6


def degree_of_affinity(player):
    """
    Afinidad (0-100) con cada compañero con el que ha jugado en pareja.
    % de puntos ganados en pareja (cada partido pesa game.score), suavizado
    hacia el 50 % cuando hay pocos partidos.
    Devuelve: [{'name', 'affinity', 'games', 'wins', 'losses'}, ...] de mayor a menor.
    """
    games = Game.objects.filter(
        Q(player_1_local=player) | Q(player_2_local=player) |
        Q(player_1_visiting=player) | Q(player_2_visiting=player),
        draft_mode=False,
        winner__in=('Local', 'Visitante'),
    )

    people = {p.id: p for p in Player.objects.filter(club=player.club).exclude(id=player.id)}
    acc = {}

    for g in games:
        if player.id in (g.player_1_local_id, g.player_2_local_id):
            side, pair = 'Local', (g.player_1_local_id, g.player_2_local_id)
        else:
            side, pair = 'Visitante', (g.player_1_visiting_id, g.player_2_visiting_id)

        partner_id = pair[1] if pair[0] == player.id else pair[0]
        if partner_id not in people:
            continue

        won = g.winner == side
        weight = g.score or 1
        a = acc.setdefault(partner_id, {'games': 0, 'wins': 0, 'stake': 0, 'won_pts': 0})
        a['games'] += 1
        a['wins'] += won
        a['stake'] += weight
        a['won_pts'] += weight if won else 0

    results = []
    for partner_id, a in acc.items():
        p = people[partner_id]
        rate = (a['won_pts'] + PRIOR_POINTS * 0.5) / (a['stake'] + PRIOR_POINTS)
        results.append({
            'name': f"{p.name} {p.last_name}",
            'affinity': round(rate * 100),
            'games': a['games'],
            'wins': a['wins'],
            'losses': a['games'] - a['wins'],
        })

    results.sort(key=lambda r: (r['affinity'], r['games']), reverse=True)
    return results


def build_game_log(player):
    """
    Una sola consulta (+1 prefetch): lista cronológica de los partidos (Game) del jugador.
    Cada elemento: {'season', 'local', 'won', 'points', 'sets_won', 'sets_lost'}
    'sets_*' son los "juegos" que suma el jugador y su rival dentro del partido.
    """
    games = (
        Game.objects
        .filter(
            Q(player_1_local=player) | Q(player_2_local=player) |
            Q(player_1_visiting=player) | Q(player_2_visiting=player),
            draft_mode=False,
        )
        .select_related('match')
        .prefetch_related('results')
        .order_by(*ORDER)
    )

    log = []
    for g in games:
        if g.winner not in ('Local', 'Visitante'):
            continue  # partido sin cerrar
        is_local = player.id in (g.player_1_local_id, g.player_2_local_id)
        won = (g.winner == 'Local') == is_local

        sets_won = sets_lost = 0
        for r in g.results.all():
            loc = sum(filter(None, [r.set1_local, r.set2_local, r.set3_local]))
            vis = sum(filter(None, [r.set1_visiting, r.set2_visiting, r.set3_visiting]))
            mine, theirs = (loc, vis) if is_local else (vis, loc)
            sets_won += mine
            sets_lost += theirs

        log.append({
            'season': g.match.season,
            'local': is_local,
            'won': won,
            'points': g.score if won else 0,
            'sets_won': sets_won,
            'sets_lost': sets_lost,
        })
    return log


def calls_by_season(player):
    """Convocatorias por temporada: ({temporada: a las que se apuntó}, {temporada: total})."""
    base = Call.objects.filter(match__club=player.club, draft_mode=False)
    total = dict(base.order_by().values_list('match__season').annotate(n=Count('id', distinct=True)))
    present = dict(
        base.filter(players__id=player.id)
        .order_by().values_list('match__season').annotate(n=Count('id', distinct=True))
    )
    return present, total


def _pct(wins, total):
    return round(wins / total * 100, 1) if total else 0


def _longest_run(results, target):
    best = run = 0
    for r in results:
        run = run + 1 if r == target else 0
        best = max(best, run)
    return best


def _current_run(results):
    """Devuelve ('V', 4) o ('D', 2). Sin partidos: (None, 0)."""
    if not results:
        return None, 0
    last, n = results[-1], 0
    for r in reversed(results):
        if r != last:
            break
        n += 1
    return ('V' if last else 'D'), n


def summarize(log):
    """Todas las métricas a partir de un log (global o de una temporada)."""
    results = [g['won'] for g in log]
    local_games = [g for g in log if g['local']]
    visiting_games = [g for g in log if not g['local']]
    local = [g['won'] for g in local_games]
    visiting = [g['won'] for g in visiting_games]

    total, wins = len(results), sum(results)
    streak_type, streak_len = _current_run(results)

    local_sets_won = sum(g['sets_won'] for g in local_games)
    local_sets_lost = sum(g['sets_lost'] for g in local_games)
    visiting_sets_won = sum(g['sets_won'] for g in visiting_games)
    visiting_sets_lost = sum(g['sets_lost'] for g in visiting_games)

    return {
        'played': total,
        'wins': wins,
        'losses': total - wins,
        'pct': _pct(wins, total),
        'points': sum(g['points'] for g in log),

        'local_played': len(local),
        'local_wins': sum(local),
        'local_losses': len(local) - sum(local),
        'local_pct': _pct(sum(local), len(local)),
        'local_sets_won': local_sets_won,
        'local_sets_lost': local_sets_lost,
        'local_sets_total': local_sets_won + local_sets_lost,

        'visiting_played': len(visiting),
        'visiting_wins': sum(visiting),
        'visiting_losses': len(visiting) - sum(visiting),
        'visiting_pct': _pct(sum(visiting), len(visiting)),
        'visiting_sets_won': visiting_sets_won,
        'visiting_sets_lost': visiting_sets_lost,
        'visiting_sets_total': visiting_sets_won + visiting_sets_lost,

        'streak_type': streak_type,
        'streak_len': streak_len,
        'best_win_streak': _longest_run(results, True),
        'worst_loss_streak': _longest_run(results, False),
        'best_local_streak': _longest_run(local, True),
        'best_visiting_streak': _longest_run(visiting, True),

        # últimos 10, el más reciente a la derecha
        'form': results[-10:],
    }


def summarize_by_season(log, calls_present, calls_total):
    """Temporadas (ascendente) con métricas, convocatorias y variación de % vs. la anterior."""
    by_season = {}
    for g in log:
        by_season.setdefault(g['season'], []).append(g)

    rows, previous = [], None
    for season in sorted(by_season, key=lambda s: int(s.split('-')[0])):
        games = by_season[season]
        wins = sum(g['won'] for g in games)
        pct = _pct(wins, len(games))
        rows.append({
            'season': season,
            'played': len(games),
            'wins': wins,
            'losses': len(games) - wins,
            'pct': pct,
            'points': sum(g['points'] for g in games),
            'calls_present': calls_present.get(season, 0),
            'calls_total': calls_total.get(season, 0),
            'delta': round(pct - previous, 1) if previous is not None else None,
        })
        previous = pct
    return rows


@club_required
@require_GET
def statistics_per_player(request):
    players = Player.objects.filter(club=request.club, in_team=True).order_by('name', 'last_name')
    player_id = request.GET.get('player')

    if not player_id or not player_id.isdigit():
        return render(request, 'player_statistics.html', {'players': players})

    # Solo jugadores del club activo: los de otros clubes dan 404
    player = get_object_or_404(Player, id=player_id, club=request.club)

    # Chips de temporada: todas las del club
    all_seasons = sorted(get_total_season(Match.objects.filter(club=request.club)),
                         key=lambda s: int(s.split('-')[0]), reverse=True)
    selected_season = request.GET.get('season')
    if selected_season not in all_seasons:
        selected_season = None

    log = build_game_log(player)
    summary = summarize(log)
    calls_present, calls_total = calls_by_season(player)
    rows = summarize_by_season(log, calls_present, calls_total)

    # Detalle de la temporada elegida
    detail = None
    if selected_season:
        detail = summarize([g for g in log if g['season'] == selected_season])
        present = calls_present.get(selected_season, 0)
        total = calls_total.get(selected_season, 0)
        detail.update({
            'calls_present': present,
            'calls_total': total,
            'calls_absent': total - present,
        })

    context = {
        'players': players,
        'selected_player': player.id,
        'player': player,
        'seasons': all_seasons,
        'selected_season': selected_season,
        's': summary,
        'd': detail,
        'seasons_asc': rows,
        'seasons_desc': list(reversed(rows)),
        # enteros para anchos de barra (evita comas decimales en style="")
        'pct_w': round(summary['pct']),
        'local_pct_w': round(summary['local_pct']),
        'visiting_pct_w': round(summary['visiting_pct']),
        # datos de los gráficos (json_script en la plantilla)
        'chart_seasons': {
            'labels': [r['season'] for r in rows],
            'wins': [r['wins'] for r in rows],
            'losses': [r['losses'] for r in rows],
            'pct': [r['pct'] for r in rows],
        },
        'chart_affinity': degree_of_affinity(player),
    }
    return render(request, 'player_statistics.html', context)


# ---------------------------------------------------------------
# ESTADÍSTICAS POR PAREJAS
# ---------------------------------------------------------------

@club_required
@require_GET
def statistics_per_pair(request):
    club_players = list(Player.objects.filter(club=request.club).order_by('name', 'last_name'))
    by_id = {p.id: p for p in club_players}
    log = pair_stats.club_game_log(request.club)
    pairs = pair_stats.all_pairs(log, club_players)

    p1_id, p2_id = request.GET.get('p1', ''), request.GET.get('p2', '')
    context = {
        'players': club_players,
        'pairs': pairs,
        'selected_p1': int(p1_id) if p1_id.isdigit() else None,
        'selected_p2': int(p2_id) if p2_id.isdigit() else None,
    }

    if context['selected_p1'] and context['selected_p2']:
        # Solo jugadores del club activo: los de otros clubes dan 404
        p1, p2 = by_id.get(context['selected_p1']), by_id.get(context['selected_p2'])
        if p1 is None or p2 is None:
            raise Http404("Jugador no encontrado")
        if p1 == p2:
            context['error'] = "Elige dos jugadores distintos."
        else:
            summary = pair_stats.pair_summary(log, p1.id, p2.id)
            context.update({
                'p1': p1,
                'p2': p2,
                's': summary,
                'pct_w': round(summary['pct']),
                'local_pct_w': round(summary['local_pct']),
                'visiting_pct_w': round(summary['visiting_pct']),
                'chart_seasons': {
                    'labels': [r['season'] for r in summary['seasons']],
                    'wins': [r['wins'] for r in summary['seasons']],
                    'losses': [r['losses'] for r in summary['seasons']],
                    'pct': [r['pct'] for r in summary['seasons']],
                },
            })

    return render(request, 'pair_statistics.html', context)


# ---------------------------------------------------------------
# ADVERTENCIAS (solo administradores)
# ---------------------------------------------------------------

ALL_SEASONS = "all"


@club_admin_required
@require_GET
def warnings_statistics(request):
    penalties = (
        Penalty.objects
        .filter(player__club=request.club, call__match__club=request.club)
        .select_related('player', 'call__match__local', 'call__match__visiting')
        .order_by('-call__match__start_date', '-id')
    )

    seasons = set(penalties.values_list('call__match__season', flat=True)) | {current_season()}
    seasons = sorted((x for x in seasons if x and x != "NONE"), reverse=True)
    selected_season = request.GET.get('season') or current_season()
    if selected_season != ALL_SEASONS:
        penalties = penalties.filter(call__match__season=selected_season)
    penalties = list(penalties)

    by_player = {}
    for pen in penalties:
        row = by_player.setdefault(pen.player_id, {'player': pen.player, 'count': 0, 'items': []})
        row['count'] += 1
        row['items'].append(pen)
    ranking = sorted(by_player.values(), key=lambda r: (-r['count'], r['player'].name, r['player'].last_name))

    return render(request, 'warnings_statistics.html', {
        'seasons': seasons,
        'selected_season': selected_season,
        'all_seasons': ALL_SEASONS,
        'penalties': penalties,
        'ranking': ranking,
        'total': len(penalties),
        'players_warned': len(by_player),
        'matches_warned': len({p.call.match_id for p in penalties}),
    })
