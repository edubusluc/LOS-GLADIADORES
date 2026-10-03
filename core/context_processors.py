"""
Procesadores de contexto: variables disponibles en todas las plantillas (club activo,
sección de la navegación y si el inicio de sesión con Google está activado).
"""
from django.conf import settings


def club(request):
    """Club activo, clubes del usuario y si es capitán del club activo."""
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
    """Sección de la navegación que se marca como activa, según la app de la vista."""
    match = getattr(request, "resolver_match", None)
    if match and match.url_name == "home":
        return {"nav_section": "home"}
    app = match.func.__module__.split(".")[0] if match else ""
    return {"nav_section": NAV_SECTIONS.get(app, "")}


def google_login(request):
    """Si se muestra el botón de iniciar sesión con Google."""
    return {"google_login_enabled": settings.GOOGLE_LOGIN_ENABLED}
