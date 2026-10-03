from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext as _


def club_required(view_func):
    """El usuario debe haber iniciado sesión y pertenecer a algún club."""
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.club is None:
            return redirect("no_club")
        return view_func(request, *args, **kwargs)
    return wrapper


def club_admin_required(view_func):
    """
    Como club_required, pero además el usuario debe ser capitán del club activo.
    A un miembro se le muestra la página «Sin permiso» (403, core/templates/403.html).
    """
    @club_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.membership.is_admin:
            raise PermissionDenied(_("Solo los capitanes del club pueden ver esta página o realizar esta acción."))
        return view_func(request, *args, **kwargs)
    return wrapper
