from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from team.models import Team
from .blocklist import is_blocked
from .models import Club, Invitation, Membership


@transaction.atomic
def create_club(name, location, admin_user, gender="", country="", division=""):
    """Crea un club con su equipo propio y deja a admin_user como capitán."""
    club = Club.objects.create(name=name)
    Team.objects.create(club=club, name=name, location=location, gender=gender, country=country,
                        division=division, is_own=True, in_group=True)
    Membership.objects.create(user=admin_user, club=club, role=Membership.ADMIN)
    return club


class InvitationError(Exception):
    pass


@transaction.atomic
def accept_invitation(invitation, user):
    """
    Da de alta a ``user`` como miembro del club de la invitación y la marca como
    usada. La invitación se bloquea mientras tanto, así un mismo enlace no puede
    usarse dos veces aunque lleguen dos peticiones a la vez.
    """
    invitation = Invitation.objects.select_for_update().select_related("club").get(pk=invitation.pk)
    if not invitation.is_valid:
        raise InvitationError(_("Esta invitación ya se ha usado o ha caducado."))
    if invitation.club.is_suspended:
        raise InvitationError(_("Este club está suspendido y no admite nuevos miembros."))
    if is_blocked(user.email):
        raise InvitationError(_("Tu email está bloqueado en Zyra y no puede unirse a clubes."))
    if Membership.objects.filter(user=user, club=invitation.club).exists():
        raise InvitationError(_("Ya eres miembro de %(club)s.") % {"club": invitation.club.name})
    membership = Membership.objects.create(user=user, club=invitation.club, role=Membership.MEMBER)
    invitation.used_by = user
    invitation.used_at = timezone.now()
    invitation.save(update_fields=["used_by", "used_at"])
    return membership
