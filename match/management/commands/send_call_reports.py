from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from call.models import ReportDelivery
from match.notifications import MAX_ATTEMPTS, deliver, due_deliveries


class Command(BaseCommand):
    help = ("Envía los informes de convocatoria pendientes y reintenta los que fallaron "
            f"(como mucho EMAIL_MAX_PER_RUN por pasada; tras {MAX_ATTEMPTS} intentos se dan por fallidos).")

    def handle(self, *args, **options):
        pending = due_deliveries(limit=settings.EMAIL_MAX_PER_RUN)
        if not pending:
            self.stdout.write("No hay informes pendientes de enviar.")
            return
        self.stdout.write(f"Informes a enviar: {len(pending)}")
        failed = []
        for delivery in deliver(pending):
            if delivery.status == ReportDelivery.SENT:
                self.stdout.write(f"Enviado: {delivery.call} a {delivery.email}")
            elif delivery.status == ReportDelivery.FAILED:
                failed.append(delivery)
                self.stdout.write(f"Fallido definitivamente: {delivery.call} a {delivery.email}: {delivery.last_error}")
            else:
                self.stdout.write(f"Error (intento {delivery.attempts} de {MAX_ATTEMPTS}, se reintentará): "
                                  f"{delivery.call} a {delivery.email}: {delivery.last_error}")
        if failed:
            raise CommandError(f"{len(failed)} informes no se han podido enviar tras {MAX_ATTEMPTS} intentos: "
                               + ", ".join(f"{d.call} a {d.email}" for d in failed)
                               + ". Los administradores pueden descargarlo o reenviarlo desde la convocatoria.")
