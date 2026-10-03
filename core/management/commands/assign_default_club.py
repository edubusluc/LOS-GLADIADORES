from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Club, Membership
from match.models import Match
from players.models import Player
from team.models import Team


class Command(BaseCommand):
    help = (
        "Pasa los datos anteriores al modo multi-club: crea (o reutiliza) un club, "
        "le asigna todos los equipos, jugadores, partidos y publicaciones sin club, "
        "marca su equipo propio y da de alta a los usuarios existentes como capitanes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--name", default="LOS GLADIADORES", help="Nombre del club y de su equipo propio.")
        parser.add_argument("--location", default="", help="Localización del equipo propio si hay que crearlo.")
        parser.add_argument(
            "--no-members", action="store_true",
            help="No crear membresías para los usuarios existentes.",
        )

    @transaction.atomic
    def handle(self, *args, name, location, no_members, **options):
        club, created = Club.objects.get_or_create(name=name)
        self.stdout.write(f"Club {'creado' if created else 'existente'}: {club} (id={club.id})")

        # Equipos antiguos (sin club). Si el club ya tiene un equipo con el mismo
        # nombre (p. ej. el equipo propio que se crea al registrar el club), se
        # fusiona en el antiguo, que es el que tiene el historial de partidos.
        n_teams = n_merged = 0
        for legacy in Team.objects.filter(club__isnull=True):
            duplicate = Team.objects.filter(club=club, name__iexact=legacy.name).first()
            if duplicate:
                self._merge(duplicate, into=legacy)
                n_merged += 1
            legacy.club = club
            legacy.save()
            n_teams += 1

        own_team = club.own_team
        if own_team is None:
            own_team = Team.objects.filter(club=club, name__iexact=name).first()
            if own_team is None:
                own_team = Team.objects.create(club=club, name=name, location=location, in_group=True)
                self.stdout.write(self.style.WARNING(
                    f"No había ningún equipo llamado {name!r}: se ha creado uno nuevo (id={own_team.id})."
                ))
            own_team.is_own = True
            own_team.save()

        n_players = Player.objects.filter(club__isnull=True).update(club=club)
        n_matches = Match.objects.filter(club__isnull=True).update(club=club)

        n_members = 0
        if not no_members:
            for user in get_user_model().objects.filter(is_active=True):
                _, new = Membership.objects.get_or_create(
                    user=user, club=club, defaults={"role": Membership.ADMIN},
                )
                n_members += new

        self.stdout.write(self.style.SUCCESS(
            f"Asignados al club: {n_teams} equipos ({n_merged} duplicados fusionados), {n_players} jugadores, "
            f"{n_matches} partidos. Equipo propio: {own_team} (id={own_team.id}). "
            f"Nuevas membresías: {n_members}."
        ))

    def _merge(self, duplicate, into):
        """Pasa jugadores y partidos de `duplicate` a `into` y borra `duplicate`."""
        Player.objects.filter(team=duplicate).update(team=into)
        Match.objects.filter(local=duplicate).update(local=into)
        Match.objects.filter(visiting=duplicate).update(visiting=into)
        if duplicate.is_own:
            into.is_own = True
            into.in_group = True
        if not into.photo and duplicate.photo:
            into.photo = duplicate.photo
            # La foto pasa a `into`: que al borrar el duplicado no se borre el fichero.
            duplicate.photo = None
        if not into.location:
            into.location = duplicate.location
        self.stdout.write(f"Fusionado el equipo duplicado {duplicate} (id={duplicate.id}) en el id={into.id}.")
        duplicate.delete()
