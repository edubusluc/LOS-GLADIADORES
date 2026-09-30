import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from backoffice.models import RequestMetric


class Command(BaseCommand):
    help = "Borra las métricas de peticiones por minuto más antiguas que --days (30 por defecto)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)

    def handle(self, *args, days, **options):
        limit = timezone.now() - datetime.timedelta(days=days)
        deleted, _ = RequestMetric.objects.filter(minute__lt=limit).delete()
        self.stdout.write(f"Borradas {deleted} filas de métricas anteriores al {limit:%Y-%m-%d}.")
