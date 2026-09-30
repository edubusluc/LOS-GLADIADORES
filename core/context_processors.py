from django.conf import settings


def club(request):
    membership = getattr(request, "membership", None)
    return {
        "current_club": getattr(request, "club", None),
        "user_memberships": getattr(request, "user_memberships", []),
        "is_club_admin": bool(membership and membership.is_admin),
    }


# Sección de la navegación a la que pertenece cada app
NAV_SECTIONS = {
    "players": "players",
    "team": "teams",
    "match": "matches",
    "call": "matches",
    "callLog": "matches",
    "penalty": "matches",
    "data_analyse": "stats",
}


def navigation(request):
    match = getattr(request, "resolver_match", None)
    if match and match.url_name == "home":
        return {"nav_section": "home"}
    app = match.func.__module__.split(".")[0] if match else ""
    return {"nav_section": NAV_SECTIONS.get(app, "")}


def google_login(request):
    return {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED}
