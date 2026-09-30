from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from players.models import SnpAccount
from players.snp import sync_club


class Command(BaseCommand):
    help = ("Descarga de SNP los puntos de los jugadores de cada club con cuenta SNP configurada "
            "(un club tras otro, con la cuenta de su capitán) y los guarda.")

    def add_arguments(self, parser):
        parser.add_argument("--club", help="Nombre o slug de un club concreto; por defecto, todos.")
        parser.add_argument("--headed", action="store_true",
                            help="Abre el navegador a la vista para seguir la ejecución (necesita pantalla).")

    def handle(self, *args, club=None, headed=False, **options):
        accounts = SnpAccount.objects.select_related("club").order_by("club__name")
        if club:
            accounts = accounts.filter(Q(club__slug=club) | Q(club__name__iexact=club))
            if not accounts:
                with_account = ", ".join(f"{a.club.name} ({a.club.slug})" for a in SnpAccount.objects.select_related("club"))
                raise CommandError(f"El club «{club}» no existe o no tiene cuenta SNP. Clubes con cuenta: {with_account or 'ninguno'}.")
        failed = 0
        for account in accounts:
            self.stdout.write(f"[{account.club}] Empezando…")
            result = sync_club(account, headed=headed, log=lambda message: self.stdout.write(f"  {message}"))
            failed += not result.ok
            self.stdout.write(f"[{account.club}] {'OK' if result.ok else 'ERROR'}")
            self.stdout.write(result.report())
            for name, score in result.updated:
                self.stdout.write(f"  {name}: {score:g}")
        self.stdout.write(f"Clubes procesados: {len(accounts)}; con error: {failed}.")
        if failed and failed == len(accounts):
            raise CommandError("No se ha podido actualizar ningún club.")
