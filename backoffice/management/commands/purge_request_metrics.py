"""Comando que borra las métricas de carga antiguas."""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from backoffice.models import RequestMetric


class Command(BaseCommand):
    """Borra las filas de RequestMetric anteriores a --days días."""
    help = "Borra las métricas de peticiones por minuto más antiguas que --days (30 por defecto)."

    def add_arguments(self, parser):
        """Añade la opción --days (30 por defecto)."""
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, days, **options):
        """Borra las métricas antiguas e informa de cuántas filas se han borrado."""
        limit = timezone.now() - datetime.timedelta(days=days)
        deleted, _ = RequestMetric.objects.filter(minute__lt=limit).delete()
        self.stdout.write(f"Borradas {deleted} filas de métricas anteriores al {limit:%Y-%m-%d}.")
