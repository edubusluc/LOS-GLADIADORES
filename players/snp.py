"""
Actualización de los puntos SNP: cruza los nombres que devuelve SNP con los jugadores
del club y guarda la puntuación. Lo usan el proceso programado ``update_snp_scores``
y el botón «Actualizar ahora» de la página de la cuenta SNP.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from django.utils import timezone

from core.crypto import DecryptionError

from .models import Player, SnpScoreHistory, current_season
from .scraper import SnpScrapeError, scrape_scores, split_category

# Coincidencia exacta > nombre completo al principio (sobra o falta el 2º apellido o la
# categoría) > nombre y primer apellido presentes.
EXACT, PREFIX, PARTIAL = 3, 2, 1


def normalize(text):
    """Sin tildes, en minúsculas y solo letras y números: 'José  Pérez-Ruíz' -> 'jose perez ruiz'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9ñ]+", " ", text).split())


def _snp_tokens(name):
    # SNP añade al final la categoría del jugador ("500", "Future", "Grand Slam"…).
    return normalize(split_category(name)[0]).split()


def _match_level(player_tokens, snp_tokens):
    if not player_tokens or not snp_tokens:
        return 0
    if player_tokens == snp_tokens:
        return EXACT
    shorter = min(len(player_tokens), len(snp_tokens))
    if len(player_tokens) >= 2 and player_tokens[:shorter] == snp_tokens[:shorter] and shorter >= 2:
        return PREFIX
    if len(player_tokens) >= 2 and player_tokens[0] == snp_tokens[0] and player_tokens[1] in snp_tokens[1:]:
        return PARTIAL
    return 0


def match_scores(players, scores):
    """
    Empareja jugadores y puntuaciones de SNP. Devuelve (emparejados, sin_jugador, ambiguos):
    emparejados es una lista de (jugador, puntos, nombre_en_snp); sin_jugador, los nombres
    de SNP que no se han podido asignar; ambiguos, los que encajan igual de bien con varios.
    """
    tokens = {p.pk: normalize(f"{p.name} {p.last_name}").split() for p in players}
    candidates = []  # (nivel, jugador, entrada de SNP)
    unmatched, ambiguous = [], []
    for entry in scores:
        snp_tokens = _snp_tokens(entry["name"])
        levels = [(_match_level(tokens[p.pk], snp_tokens), p) for p in players]
        best = max((level for level, _ in levels), default=0)
        best_players = [p for level, p in levels if level == best and level > 0]
        if not best_players:
            unmatched.append(entry["name"])
        elif len(best_players) > 1:
            ambiguous.append(entry["name"])
        else:
            candidates.append((best, best_players[0], entry))

    # Un jugador solo puede recibir una puntuación: la de la coincidencia más clara.
    by_player = {}
    for level, player, entry in candidates:
        by_player.setdefault(player.pk, []).append((level, player, entry))
    matched = []
    for options in by_player.values():
        options.sort(key=lambda o: o[0], reverse=True)
        if len(options) > 1 and options[0][0] == options[1][0]:
            ambiguous.extend(o[2]["name"] for o in options)
            continue
        level, player, entry = options[0]
        matched.append((player, entry["score"], entry["name"]))
        unmatched.extend(o[2]["name"] for o in options[1:])
    return matched, unmatched, ambiguous


@dataclass
class SyncResult:
    ok: bool
    message: str
    total: int = 0
    updated: list = field(default_factory=list)
    unmatched: list = field(default_factory=list)
    ambiguous: list = field(default_factory=list)
    missing: list = field(default_factory=list)

    def report(self):
        lines = [self.message]
        if self.unmatched:
            lines.append("En SNP pero sin jugador en Zyra: " + ", ".join(self.unmatched))
        if self.ambiguous:
            lines.append("Nombres que encajan con varios jugadores (no se han tocado): " + ", ".join(self.ambiguous))
        if self.missing:
            lines.append("Jugadores de Zyra que no aparecen en SNP: " + ", ".join(self.missing))
        return "\n".join(lines)


def sync_club(account, scraper=None, **scrape_options):
    """Descarga los puntos SNP del club de ``account`` y los guarda. Nunca lanza: devuelve un SyncResult."""
    try:
        scores = (scraper or scrape_scores)(account.username, account.password, account.team_id or None, **scrape_options)
    except (SnpScrapeError, DecryptionError) as exc:
        result = SyncResult(ok=False, message=str(exc))
    else:
        players = list(Player.objects.filter(club=account.club, in_team=True))
        matched, unmatched, ambiguous = match_scores(players, scores)
        today, season = timezone.localdate(), current_season()
        for player, score, _ in matched:
            if player.snp_score != score:
                player.snp_score = score
                player.save(update_fields=["snp_score"])
            # Histórico para el gráfico de la temporada: un punto por jugador y día.
            SnpScoreHistory.objects.update_or_create(
                player=player, date=today, defaults={"score": score, "season": season},
            )
        matched_ids = {p.pk for p, _, _ in matched}
        result = SyncResult(
            ok=True,
            message=f"{len(matched)} de {len(players)} jugadores actualizados con los puntos de SNP.",
            total=len(players),
            updated=[(str(p), score) for p, score, _ in matched],
            unmatched=unmatched, ambiguous=ambiguous,
            missing=[str(p) for p in players if p.pk not in matched_ids],
        )
    account.last_sync_at = timezone.now()
    account.last_sync_ok = result.ok
    account.last_sync_message = result.report()
    account.save(update_fields=["last_sync_at", "last_sync_ok", "last_sync_message"])
    return result
