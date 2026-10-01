from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
    """Como club_required, pero además el usuario debe ser administrador del club activo."""
    @club_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.membership.is_admin:
            messages.error(request, _("Solo los administradores del club pueden realizar esta acción."))
            return redirect("home")
        return view_func(request, *args, **kwargs)
    return wrapper
