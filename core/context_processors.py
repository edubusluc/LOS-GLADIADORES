def club(request):
    membership = getattr(request, "membership", None)
    return {
        "current_club": getattr(request, "club", None),
        "user_memberships": getattr(request, "user_memberships", []),
        "is_club_admin": bool(membership and membership.is_admin),
    }


# Sección de la navegación a la que pertenece cada app
NAV_SECTIONS = {
    "post": "home",
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
    app = match.func.__module__.split(".")[0] if match else ""
    return {"nav_section": NAV_SECTIONS.get(app, "")}
