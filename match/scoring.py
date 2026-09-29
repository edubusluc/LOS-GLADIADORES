"""
Reglas de puntuación de un partido de pádel (al mejor de 3 sets).

- Un set se gana 6-0, 6-1, 6-2, 6-3, 6-4, 7-5 o 7-6 (tie-break).
- Si una pareja gana los dos primeros sets, no se juega el tercero.
- Si se reparten los dos primeros, el tercero es obligatorio y puede ser un
  set normal o, si ALLOW_SUPER_TIEBREAK está activo, un super tie-break a 10
  puntos con 2 de diferencia (10-8, 11-9, 12-10...).
"""
from django.core.exceptions import ValidationError

ALLOW_SUPER_TIEBREAK = True
SUPER_TIEBREAK_POINTS = 10

VALID_SET_SCORES = sorted(
    {(6, n) for n in range(5)} | {(7, 5), (7, 6)}
)
SET_RULE = "Un set se gana 6-0, 6-1, 6-2, 6-3, 6-4, 7-5 o 7-6."


def to_int(value):
    """'6' -> 6; '' o None -> None. Lanza ValidationError si no es un número >= 0."""
    if value in (None, ""):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{value}' no es un número.")
    if n < 0:
        raise ValidationError("Los juegos no pueden ser negativos.")
    return n


def is_valid_set(a, b):
    return (max(a, b), min(a, b)) in VALID_SET_SCORES


def is_valid_super_tiebreak(a, b):
    high, low = max(a, b), min(a, b)
    if high < SUPER_TIEBREAK_POINTS:
        return False
    # A 10 se gana con 2 de ventaja; si se pasa de 10, la diferencia es exactamente 2
    return high - low >= 2 if high == SUPER_TIEBREAK_POINTS else high - low == 2


def set_winner(a, b):
    return "local" if a > b else "visiting"


def validate_padel_result(set1, set2, set3):
    """
    Valida un resultado (cada set es una tupla (local, visitante) de enteros o None).
    Devuelve (sets_normalizados, ganador) con ganador 'local' o 'visiting'.
    Lanza ValidationError con un mensaje por cada problema encontrado.
    """
    errors = []
    sets = [set1, set2, set3]

    for n, (a, b) in enumerate(sets[:2], start=1):
        if a is None or b is None:
            errors.append(f"Set {n}: falta el resultado.")
        elif not is_valid_set(a, b):
            errors.append(f"Set {n}: {a}-{b} no es un resultado válido. {SET_RULE}")
    if errors:
        raise ValidationError(errors)

    w1, w2 = set_winner(*set1), set_winner(*set2)
    a3, b3 = set3
    third_played = not (a3 in (None, 0) and b3 in (None, 0))

    if w1 == w2:
        if third_played:
            raise ValidationError(
                "Set 3: no se juega si la misma pareja ha ganado los dos primeros sets. Déjalo vacío."
            )
        return [set1, set2, (None, None)], w1

    if not third_played or a3 is None or b3 is None:
        raise ValidationError("Set 3: con un set para cada pareja, el tercero es obligatorio.")
    if is_valid_set(a3, b3):
        return sets, set_winner(a3, b3)
    if ALLOW_SUPER_TIEBREAK and is_valid_super_tiebreak(a3, b3):
        return sets, set_winner(a3, b3)

    rule = SET_RULE
    if ALLOW_SUPER_TIEBREAK:
        rule += f" También vale un super tie-break a {SUPER_TIEBREAK_POINTS} puntos con 2 de diferencia (10-8, 11-9...)."
    raise ValidationError(f"Set 3: {a3}-{b3} no es un resultado válido. {rule}")
