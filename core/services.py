from django.db import transaction

from team.models import Team
from .models import Club, Membership


@transaction.atomic
def create_club(name, location, admin_user):
    """Crea un club con su equipo propio y deja a admin_user como administrador."""
    club = Club.objects.create(name=name)
    Team.objects.create(club=club, name=name, location=location, is_own=True, in_group=True)
    Membership.objects.create(user=admin_user, club=club, role=Membership.ADMIN)
    return club
