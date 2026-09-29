from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Club, Membership
from match.models import Match
from players.models import Player
from post.models import Post
from team.models import Team


class Command(BaseCommand):
    help = (
        "Pasa los datos anteriores al modo multi-club: crea (o reutiliza) un club, "
        "le asigna todos los equipos, jugadores, partidos y publicaciones sin club, "
        "marca su equipo propio y da de alta a los usuarios existentes como administradores."
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

        n_teams = Team.objects.filter(club__isnull=True).update(club=club)

        own_team = club.own_team
        if own_team is None:
            own_team = Team.objects.filter(club=club, name__iexact=name).first()
            if own_team is None:
                own_team = Team.objects.create(club=club, name=name, location=location, in_group=True)
            own_team.is_own = True
            own_team.save()

        n_players = Player.objects.filter(club__isnull=True).update(club=club)
        n_matches = Match.objects.filter(club__isnull=True).update(club=club)
        n_posts = Post.objects.filter(club__isnull=True).update(club=club)

        n_members = 0
        if not no_members:
            for user in get_user_model().objects.filter(is_active=True):
                _, new = Membership.objects.get_or_create(
                    user=user, club=club, defaults={"role": Membership.ADMIN},
                )
                n_members += new

        self.stdout.write(self.style.SUCCESS(
            f"Asignados al club: {n_teams} equipos, {n_players} jugadores, {n_matches} partidos, "
            f"{n_posts} publicaciones. Equipo propio: {own_team}. Nuevas membresías: {n_members}."
        ))
