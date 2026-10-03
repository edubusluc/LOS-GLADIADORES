"""Comando que rellena la ubicación de los partidos antiguos con la sede del equipo local."""
from django.core.management.base import BaseCommand

from match.models import Match


class Command(BaseCommand):
    """Copia la sede del equipo local en los partidos sin ubicación."""
    help = "Copia la ubicación del equipo local en los partidos que aún no tienen ubicación."

    def handle(self, *args, **options):
        """Rellena la ubicación de los partidos que no tienen y muestra cuántos se han actualizado."""
        n = 0
        for match in Match.objects.filter(location="", local__isnull=False).exclude(local__location="").select_related("local"):
            match.location = match.local.location
            match.save(update_fields=["location"])
            n += 1
        self.stdout.write(self.style.SUCCESS(f"Partidos actualizados: {n}."))
