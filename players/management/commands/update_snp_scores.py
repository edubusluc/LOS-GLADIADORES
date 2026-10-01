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
                            help="Abre el navegador a la vista para seguir la ejecución (necesita pantalla). "
                                 "Con --headed o -v 2 se muestran también los pasos y los puntos de cada jugador.")

    def handle(self, *args, club=None, headed=False, **options):
        accounts = SnpAccount.objects.select_related("club").order_by("club__name")
        if club:
            accounts = accounts.filter(Q(club__slug=club) | Q(club__name__iexact=club))
            if not accounts:
                with_account = ", ".join(f"{a.club.name} ({a.club.slug})" for a in SnpAccount.objects.select_related("club"))
                raise CommandError(f"El club «{club}» no existe o no tiene cuenta SNP. Clubes con cuenta: {with_account or 'ninguno'}.")
        verbose = options["verbosity"] >= 2 or headed
        self.stdout.write(f"Equipos a actualizar: {len(accounts)}")
        failed = 0
        for account in accounts:
            self.stdout.write("")
            self.stdout.write(f"Equipo que se actualiza: {account.club}")
            log = (lambda message: self.stdout.write(f"  {message}")) if verbose else None
            result = sync_club(account, headed=headed, log=log)
            if not result.ok:
                failed += 1
                self.stdout.write(f"Error: {result.message}")
                continue
            self.stdout.write(f"Jugadores a actualizar: {result.total}")
            self.stdout.write(f"Jugadores actualizados correctamente: {len(result.updated)}")
            missing = f" ({', '.join(result.missing)})" if result.missing else ""
            self.stdout.write(f"Jugadores no actualizados: {len(result.missing)}{missing}")
            if verbose:
                for name, score in result.updated:
                    self.stdout.write(f"  {name}: {score:g}")
                if result.unmatched:
                    self.stdout.write("  En SNP pero sin jugador en Zyra: " + ", ".join(result.unmatched))
        if failed and failed == len(accounts):
            raise CommandError("No se ha podido actualizar ningún equipo.")
