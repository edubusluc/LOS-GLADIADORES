"""Comando assign_public_ids: rellena el public_id de las filas que no lo tienen."""
from django.core.management.base import BaseCommand
from django.db import transaction

from core.public_id import new_public_id, public_id_models


class Command(BaseCommand):
    """Asigna public_id a las filas existentes de todos los modelos que lo tienen."""
    help = (
        "Asigna un identificador público (core/public_id.py) a las filas que todavía no "
        "lo tienen. Se lanza una vez después de migrar; volver a lanzarlo no cambia nada."
    )

    def add_arguments(self, parser):
        """Opción --dry-run."""
        parser.add_argument("--dry-run", action="store_true", help="Solo cuenta las filas sin identificador.")

    def handle(self, *args, dry_run=False, **options):
        """
        Recorre los modelos con public_id y rellena las filas que no lo tienen (con update(),
        fila a fila); con --dry-run solo las cuenta.
        """
        total = 0
        for model in public_id_models():
            pending = model._default_manager.filter(public_id__isnull=True)
            count = pending.count()
            if not count:
                continue
            total += count
            if not dry_run:
                with transaction.atomic():
                    for pk in pending.values_list("pk", flat=True):
                        # update() y no save(): no dispara la lógica de save() de cada modelo
                        # (temporada del partido, validación del resultado...).
                        model._default_manager.filter(pk=pk).update(public_id=new_public_id(model.PUBLIC_ID_PREFIX))
            self.stdout.write(f"{model._meta.label}: {count} fila{'s' if count != 1 else ''}")

        verb = "sin identificador" if dry_run else "con identificador nuevo"
        self.stdout.write(self.style.SUCCESS(f"Total: {total} fila{'s' if total != 1 else ''} {verb}."))
