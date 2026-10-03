"""Comando que borra el log antiguo de ejecuciones de procesos."""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from backoffice.models import JobRun


class Command(BaseCommand):
    """Borra las ejecuciones terminadas anteriores a --days días (las que están en curso, nunca)."""
    help = "Borra el log de ejecuciones de procesos más antiguo que --days (90 por defecto)."

    def add_arguments(self, parser):
        """Añade la opción --days (90 por defecto)."""
        parser.add_argument("--days", type=int, default=90)

    def handle(self, *args, days, **options):
        """Borra las ejecuciones antiguas e informa de cuántas se han borrado."""
        limit = timezone.now() - datetime.timedelta(days=days)
        deleted, _ = JobRun.objects.filter(started_at__lt=limit).exclude(status=JobRun.RUNNING).delete()
        self.stdout.write(f"Borradas {deleted} ejecuciones anteriores al {limit:%Y-%m-%d}.")
