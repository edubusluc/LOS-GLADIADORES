"""
Alineación de un enfrentamiento: las 5 parejas del club y el orden de los partidos.

Se valida y se guarda siempre la alineación completa, en una transacción: o se
guardan los 5 partidos o ninguno. Así no pueden quedar partidos a medias ni
duplicados.
"""
import json

from django.db import transaction

from .models import Game

GAMES_PER_MATCH = 5


class LineupError(Exception):
    pass


def game_points(index):
    """Puntos en juego según el orden del partido: los dos primeros valen 3, el resto 2."""
    return 3 if index in (1, 2) else 2


def parse_lineup(raw, call, match_games=None):
    """
    Convierte el JSON del formulario en una lista ordenada de
    (juego_existente_o_None, jugador_1, jugador_2). Lanza LineupError si algo no cuadra.
    """
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        raise LineupError("Los datos de la alineación no son válidos.")
    if not isinstance(data, list) or len(data) != GAMES_PER_MATCH:
        raise LineupError(f"Hay que completar las {GAMES_PER_MATCH} parejas antes de guardar.")

    called = {p.id: p for p in call.players.all()}
    games_by_id = {g.id: g for g in (match_games or [])}
    used_players, used_games, lineup = set(), set(), []

    for n, item in enumerate(data, start=1):
        try:
            p1, p2 = called[int(item["player1Id"])], called[int(item["player2Id"])]
        except (KeyError, TypeError, ValueError):
            raise LineupError(f"Partido {n}: los dos jugadores deben estar en la convocatoria.")
        if p1 == p2:
            raise LineupError(f"Partido {n}: una pareja necesita dos jugadores distintos.")
        for p in (p1, p2):
            if p.id in used_players:
                raise LineupError(f"{p} aparece en más de una pareja.")
            used_players.add(p.id)

        game = None
        if match_games is not None:
            try:
                game = games_by_id[int(item["gameId"])]
            except (KeyError, TypeError, ValueError):
                raise LineupError("La alineación no corresponde a los partidos de este enfrentamiento.")
            if game.id in used_games:
                raise LineupError("La alineación no corresponde a los partidos de este enfrentamiento.")
            used_games.add(game.id)
        lineup.append((game, p1, p2))

    return lineup


def _assign(game, match, n, p1, p2):
    side, other = ("local", "visiting") if match.own_is_local else ("visiting", "local")
    setattr(game, f"player_1_{side}", p1)
    setattr(game, f"player_2_{side}", p2)
    setattr(game, f"player_1_{other}", None)
    setattr(game, f"player_2_{other}", None)
    game.n_game = n
    game.score = game_points(n)


@transaction.atomic
def create_games(match, lineup):
    if not (match.own_is_local or match.own_is_visiting):
        raise LineupError("El enfrentamiento no es del equipo del club.")
    # Bloquea el enfrentamiento para que dos envíos a la vez no creen partidos dobles
    type(match).objects.select_for_update().get(pk=match.pk)
    if Game.objects.filter(match=match).exists():
        raise LineupError("Los partidos de este enfrentamiento ya estaban creados.")
    games = []
    for n, (_, p1, p2) in enumerate(lineup, start=1):
        game = Game(match=match, draft_mode=True, winner=None)
        _assign(game, match, n, p1, p2)
        games.append(game)
    Game.objects.bulk_create(games)
    return games


@transaction.atomic
def update_games(match, lineup):
    games = [g for g, _, _ in lineup]
    # Primero se libera el número de cada partido para poder reordenarlos sin
    # chocar con la restricción de número único por enfrentamiento.
    Game.objects.filter(pk__in=[g.pk for g in games]).update(n_game=None)
    for n, (game, p1, p2) in enumerate(lineup, start=1):
        _assign(game, match, n, p1, p2)
        game.save()
    return games
