"""
Copia todos los datos de un fichero SQLite de Zyra a la base de datos configurada
(PostgreSQL, con DATABASE_URL) y comprueba que no se ha perdido nada.

Pasos:

1. Comprueba que el destino es PostgreSQL, que ya tiene las tablas (``migrate``) y que
   está vacío: nunca mezcla datos ni sobrescribe nada.
2. Comprueba que el SQLite de origen tiene aplicadas las mismas migraciones que el código
   (si no, primero ``adopt_repo_migrations`` y ``migrate`` sobre ese SQLite).
3. Exporta los datos del SQLite y los carga en el destino en una sola transacción: o se
   copia todo o nada. Las tablas de permisos y tipos de contenido no se copian (las crea
   ``migrate``); las relaciones con ellas se resuelven por nombre.
4. Cuenta las filas de cada tabla en origen y destino y avisa si alguna no coincide.

El SQLite de origen no se modifica.
"""
import copy
import os
import tempfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

SOURCE = "sqlite_source"
# Las crea migrate en el destino; copiarlas chocaría con las que ya existen.
EXCLUDED = ["contenttypes", "auth.permission"]


def _models():
    """Modelos con datos propios (sin los excluidos ni los proxy)."""
    for model in apps.get_models(include_auto_created=True):
        meta = model._meta
        if meta.proxy or not meta.managed:
            continue
        if meta.app_label == "contenttypes" or meta.label_lower == "auth.permission":
            continue
        yield model


def _counts(alias):
    return {model._meta.label: model._default_manager.using(alias).count() for model in _models()}


class Command(BaseCommand):
    help = ("Copia los datos de un fichero SQLite de Zyra a la base de datos configurada (PostgreSQL) "
            "y comprueba que el número de filas de cada tabla coincide.")

    def add_arguments(self, parser):
        parser.add_argument("sqlite_path", nargs="?", default=str(settings.BASE_DIR / "db.sqlite3"),
                            help="Fichero SQLite de origen (por defecto, db.sqlite3 junto a manage.py).")
        parser.add_argument("--any-target", action="store_true",
                            help="Permite un destino que no sea PostgreSQL (solo para pruebas).")

    def handle(self, *args, sqlite_path, any_target=False, **options):
        target = connections[DEFAULT_DB_ALIAS]
        path = Path(sqlite_path).resolve()
        if not path.is_file():
            raise CommandError(f"No existe el fichero SQLite {path}.")
        if target.vendor != "postgresql" and not any_target:
            raise CommandError(
                "El destino no es PostgreSQL. Define DATABASE_URL (p. ej. postgres://zyra:zyra@localhost:5432/zyra) "
                "y ejecuta antes python manage.py migrate."
            )
        if target.vendor == "sqlite" and Path(str(target.settings_dict["NAME"])).resolve() == path:
            raise CommandError("El origen y el destino son el mismo fichero.")

        self._add_source(path)
        try:
            self._check_migrations()
            self._check_target_empty()
            source_counts = _counts(SOURCE)
            self.stdout.write(f"Origen: {path} ({sum(source_counts.values())} filas)")
            self._copy()
            self._verify(source_counts)
        finally:
            connections[SOURCE].close()
            del connections.databases[SOURCE]

    def _add_source(self, path):
        databases = {
            DEFAULT_DB_ALIAS: copy.deepcopy(settings.DATABASES[DEFAULT_DB_ALIAS]),
            SOURCE: {"ENGINE": "django.db.backends.sqlite3", "NAME": str(path)},
        }
        connections.databases[SOURCE] = connections.configure_settings(databases)[SOURCE]

    def _check_migrations(self):
        """Origen y destino deben tener aplicadas todas las migraciones del código."""
        def pending(alias):
            executor = MigrationExecutor(connections[alias])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            return [f"{m.app_label}.{m.name}" for m, _ in plan]

        missing = pending(DEFAULT_DB_ALIAS)
        if missing:
            raise CommandError("Al destino le faltan migraciones: ejecuta antes python manage.py migrate "
                               f"({', '.join(missing[:5])}).")
        missing = pending(SOURCE)
        if missing:
            raise CommandError(
                "Al SQLite de origen le faltan migraciones del código, así que sus tablas no coinciden con "
                "las del destino. Ponlo al día antes (con ese fichero como db.sqlite3 y sin DATABASE_URL): "
                "python manage.py adopt_repo_migrations y python manage.py migrate. Faltan: " + ", ".join(missing[:8])
            )

    def _check_target_empty(self):
        filled = {label: n for label, n in _counts(DEFAULT_DB_ALIAS).items() if n}
        if filled:
            detail = ", ".join(f"{label} ({n})" for label, n in sorted(filled.items())[:8])
            raise CommandError(f"El destino ya tiene datos ({detail}). Solo se copia a una base de datos vacía "
                               "(recién creada y con migrate).")

    def _copy(self):
        fd, dump = tempfile.mkstemp(suffix=".json", prefix="zyra-copia-")
        os.close(fd)
        try:
            self.stdout.write("Exportando datos del SQLite…")
            call_command("dumpdata", database=SOURCE, natural_foreign=True, exclude=EXCLUDED,
                         output=dump, verbosity=0)
            self.stdout.write("Cargando en el destino (todo o nada)…")
            call_command("loaddata", dump, database=DEFAULT_DB_ALIAS, verbosity=0)
        finally:
            os.remove(dump)

    def _verify(self, source_counts):
        target_counts = _counts(DEFAULT_DB_ALIAS)
        wrong = []
        self.stdout.write("")
        self.stdout.write(f"{'Tabla':45} {'Origen':>8} {'Destino':>8}")
        for label in sorted(source_counts):
            src, dst = source_counts[label], target_counts.get(label, 0)
            if src or dst:
                mark = "" if src == dst else "  <-- NO COINCIDE"
                self.stdout.write(f"{label:45} {src:>8} {dst:>8}{mark}")
            if src != dst:
                wrong.append(label)
        if wrong:
            raise CommandError("La copia no coincide en: " + ", ".join(wrong))
        self.stdout.write(self.style.SUCCESS(f"Copia completa: {sum(target_counts.values())} filas, todas las tablas coinciden."))
