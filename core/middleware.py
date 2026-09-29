from .models import Membership

SESSION_KEY = "club_id"


class CurrentClubMiddleware:
    """
    Resuelve el club activo del usuario y lo deja en request.club / request.membership.

    El club activo se guarda en sesión; si no hay ninguno (o el guardado ya no es
    válido) se usa la primera membresía del usuario. Un usuario sin membresías
    tiene request.club = None.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.club = None
        request.membership = None

        if request.user.is_authenticated:
            memberships = Membership.objects.filter(user=request.user).select_related("club").order_by("club__name")
            club_id = request.session.get(SESSION_KEY)
            membership = None
            if club_id:
                membership = next((m for m in memberships if m.club_id == club_id), None)
            if membership is None:
                membership = memberships.first()

            if membership:
                request.membership = membership
                request.club = membership.club
                if club_id != membership.club_id:
                    request.session[SESSION_KEY] = membership.club_id
            request.user_memberships = memberships
        else:
            request.user_memberships = []

        return self.get_response(request)
