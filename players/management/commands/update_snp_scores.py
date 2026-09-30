from django.core.management.base import BaseCommand, CommandError

from players.models import SnpAccount
from players.snp import sync_club


class Command(BaseCommand):
    help = ("Descarga de SNP los puntos de los jugadores de cada club con cuenta SNP configurada "
            "(un club tras otro, con la cuenta de su capitán) y los guarda.")

    def add_arguments(self, parser):
        parser.add_argument("--club", help="Slug de un club concreto; por defecto, todos.")

    def handle(self, *args, club=None, **options):
        accounts = SnpAccount.objects.select_related("club").order_by("club__name")
        if club:
            accounts = accounts.filter(club__slug=club)
            if not accounts:
                raise CommandError(f"El club «{club}» no existe o no tiene cuenta SNP.")
        failed = 0
        for account in accounts:
            result = sync_club(account)
            failed += not result.ok
            self.stdout.write(f"[{account.club}] {'OK' if result.ok else 'ERROR'}")
            self.stdout.write(result.report())
        self.stdout.write(f"Clubes procesados: {len(accounts)}; con error: {failed}.")
        if failed and failed == len(accounts):
            raise CommandError("No se ha podido actualizar ningún club.")
