from django.core.management.base import BaseCommand

from backoffice.scheduler import run_due_jobs


class Command(BaseCommand):
    help = "Lanza los procesos programados a los que les toca. Ejecútalo cada minuto (cron o similar)."

    def handle(self, *args, **options):
        runs = run_due_jobs()
        for run in runs:
            self.stdout.write(f"{run.job.name}: {run.get_status_display()}")
        if not runs:
            self.stdout.write("Nada que ejecutar.")
