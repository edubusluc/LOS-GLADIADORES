"""
Mueve las fotos antiguas de equipos y jugadores al almacenamiento de fotos (media/).

Antes las fotos subidas se guardaban dentro de static/ (static/team, static/profile). Este
comando coge cada foto cuya ruta no está aún en teams/ o players/, la procesa como una
subida nueva (reducida y en WebP, ver core/images.py), la guarda en el almacenamiento y
corrige la ruta en la base de datos. Después borra el original de static/ (salvo con
--keep-originals). Las fotos de ejemplo de populate/ nunca se borran.

    python manage.py move_photos_to_media --dry-run   # solo dice qué haría
    python manage.py move_photos_to_media

Se puede ejecutar varias veces: lo ya movido no se vuelve a tocar.
"""
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import transaction

from core.images import PHOTO_DIRS, process_image
from core.models import PhotoCheck
from players.models import Player
from team.models import Team


class Command(BaseCommand):
    """Mueve las fotos antiguas de static/ al almacenamiento de fotos."""
    help = "Mueve las fotos de equipos y jugadores guardadas en static/ al almacenamiento de fotos (media/)."

    def add_arguments(self, parser):
        """Opciones --dry-run y --keep-originals."""
        parser.add_argument("--dry-run", action="store_true", help="No cambia nada, solo dice qué haría.")
        parser.add_argument("--keep-originals", action="store_true", help="No borra los ficheros originales de static/.")

    def handle(self, *args, dry_run=False, keep_originals=False, **options):
        """
        Procesa y guarda cada foto antigua de equipos y jugadores, corrige su ruta (también en
        PhotoCheck) y al final borra los originales de static/ salvo con --keep-originals.
        """
        base = Path(settings.BASE_DIR).resolve()
        moved = missing = invalid = 0
        to_delete = set()
        for model in (Team, Player):
            field = model._meta.get_field("photo")
            names = (
                model.objects.exclude(photo__isnull=True).exclude(photo="")
                .values_list("photo", flat=True).distinct()
            )
            for name in sorted(names):
                if name.startswith(tuple(f"{d}/" for d in PHOTO_DIRS)):
                    continue
                rows = model.objects.filter(photo=name)
                source = self._find(name, base)
                if source is None:
                    missing += 1
                    self.stdout.write(self.style.WARNING(f"No se encuentra {name} ({rows.count()} {model._meta.verbose_name_plural}): se deja igual."))
                    continue
                if dry_run:
                    moved += 1
                    self.stdout.write(f"Se movería {name} ({rows.count()} {model._meta.verbose_name_plural}).")
                    continue
                try:
                    with source.open("rb") as f:
                        content = process_image(f)
                except ValidationError:
                    invalid += 1
                    self.stdout.write(self.style.WARNING(f"{name} no es una imagen válida: se deja igual."))
                    continue
                new_name = default_storage.save(field.generate_filename(None, "photo.webp"), content)
                with transaction.atomic():
                    # update() no lanza las señales de core/images.py, que borrarían el original.
                    n = rows.update(photo=new_name)
                    PhotoCheck.objects.filter(photo=name).update(photo=new_name)
                moved += 1
                self.stdout.write(f"{name} -> {new_name} ({n} {model._meta.verbose_name_plural}).")
                if isinstance(source, Path) and self._in_static(source, base):
                    to_delete.add(source)

        if not keep_originals:
            for path in sorted(to_delete):
                path.unlink(missing_ok=True)
                self.stdout.write(f"Borrado {path.relative_to(base)}.")

        prefix = "[simulación] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Fotos movidas: {moved}. No encontradas: {missing}. No válidas: {invalid}."
        ))

    def _find(self, name, base):
        """El fichero de una ruta antigua: en el almacenamiento o, si no, junto a manage.py."""
        try:
            if default_storage.exists(name):
                return _StorageFile(name)
        except SuspiciousFileOperation:  # ruta fuera del almacenamiento (../)
            pass
        path = (base / name).resolve()
        if path.is_relative_to(base) and path.is_file():
            return path
        return None

    @staticmethod
    def _in_static(path, base):
        """True si ``path`` está dentro de static/ o de algún STATICFILES_DIRS."""
        return any(path.is_relative_to((base / d).resolve()) for d in [*settings.STATICFILES_DIRS, "static"])


class _StorageFile:
    """Ruta dentro del almacenamiento con la misma interfaz open() que Path."""

    def __init__(self, name):
        """``name``: ruta del fichero dentro del almacenamiento."""
        self.name = name

    def open(self, mode="rb"):
        """Abre el fichero del almacenamiento."""
        return default_storage.open(self.name, mode)
