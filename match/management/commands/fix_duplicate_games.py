"""Comando de mantenimiento: borra partidos y resultados duplicados antes de las restricciones de unicidad."""
from django.core.management.base import BaseCommand
from django.db import transaction

from match.models import Game, Result


class Command(BaseCommand):
    """Borra partidos y resultados duplicados (ver ``help``)."""
    help = (
        "Elimina los partidos (Game) duplicados de un enfrentamiento y los resultados "
        "duplicados de un partido. De cada número de partido se conserva el que tiene "
        "resultado y, si hay varios, el más reciente. Hay que ejecutarlo ANTES de migrar "
        "las restricciones de unicidad."
    )

    def add_arguments(self, parser):
        """Opción --dry-run para ver qué se borraría sin borrar nada."""
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que se borraría.")

    @transaction.atomic
    def handle(self, *args, dry_run, **options):
        """Busca y borra los duplicados en una transacción.

        De los resultados de un partido se conserva el más reciente; de los partidos con
        el mismo número, el que tiene resultado y, si hay varios, el más reciente.
        """
        to_delete_games, to_delete_results = [], []

        # 1) Resultados duplicados del mismo partido: se conserva el más reciente
        by_game = {}
        for r in Result.objects.order_by("game_id", "-id"):
            if r.game_id in by_game:
                to_delete_results.append(r)
            else:
                by_game[r.game_id] = r

        # 2) Partidos duplicados (mismo enfrentamiento y número)
        groups = {}
        for g in Game.objects.exclude(n_game__isnull=True).select_related("match").order_by("match_id", "n_game", "id"):
            groups.setdefault((g.match_id, g.n_game), []).append(g)
        for (match_id, n_game), games in groups.items():
            if len(games) < 2:
                continue
            keep = max(games, key=lambda g: (g.id in by_game, g.id))
            for g in games:
                if g is not keep:
                    to_delete_games.append(g)
            self.stdout.write(
                f"Enfrentamiento {games[0].match} (id={match_id}), partido {n_game}: "
                f"se conserva id={keep.id}, se borra{'n' if len(games) > 2 else ''} "
                + ", ".join(f"id={g.id}" for g in games if g is not keep)
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[prueba] Se borrarían {len(to_delete_games)} partidos y {len(to_delete_results)} resultados duplicados."
            ))
            transaction.set_rollback(True)
            return

        Result.objects.filter(pk__in=[r.pk for r in to_delete_results]).delete()
        Game.objects.filter(pk__in=[g.pk for g in to_delete_games]).delete()
        self.stdout.write(self.style.SUCCESS(
            f"Borrados {len(to_delete_games)} partidos y {len(to_delete_results)} resultados duplicados."
        ))
