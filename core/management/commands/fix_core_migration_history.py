from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

from core.models import Club, Membership


class Command(BaseCommand):
    help = (
        "Repara el error 'match.0002_match_club is applied before its dependency core.0001_initial'. "
        "Ocurre cuando se migró antes de que existiera core/migrations: Django creó las tablas de core "
        "sin registrar la migración. Crea las tablas que falten y marca core.0001_initial como aplicada."
    )

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        if ("core", "0001_initial") in recorder.applied_migrations():
            self.stdout.write("core.0001_initial ya estaba registrada; no hay nada que reparar.")
            return

        tables = connection.introspection.table_names()
        with connection.schema_editor() as editor:
            for model in (Club, Membership):
                if model._meta.db_table in tables:
                    self.stdout.write(f"La tabla {model._meta.db_table} ya existe.")
                else:
                    editor.create_model(model)
                    self.stdout.write(f"Tabla {model._meta.db_table} creada.")

        recorder.record_applied("core", "0001_initial")
        self.stdout.write(self.style.SUCCESS(
            "core.0001_initial marcada como aplicada. Ahora ejecuta: python manage.py migrate"
        ))
