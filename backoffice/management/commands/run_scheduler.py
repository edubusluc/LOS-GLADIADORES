"""Comando del lanzador de procesos programados (se ejecuta cada minuto)."""
from django.core.management.base import BaseCommand

from backoffice.scheduler import run_due_jobs


class Command(BaseCommand):
    """Una pasada del lanzador de procesos programados."""
    help = "Lanza los procesos programados a los que les toca. Ejecútalo cada minuto (cron o similar)."

    def handle(self, *args, **options):
        """Lanza los procesos a los que les toca y escribe el estado de cada ejecución."""
        runs = run_due_jobs()
        for run in runs:
            self.stdout.write(f"{run.job.name}: {run.get_status_display()}")
        if not runs:
            self.stdout.write("Nada que ejecutar.")
