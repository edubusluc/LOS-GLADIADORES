from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.utils import translation


def staff_required(view_func):
    """
    Solo el personal de Zyra (usuarios con is_staff) entra en el back-office.
    A cualquier otro usuario con sesión se le responde 404 para no desvelar que existe.
    El back-office se muestra siempre en español (fechas y "hace 2 días").
    """
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_active and request.user.is_staff):
            raise Http404
        with translation.override("es"):
            return view_func(request, *args, **kwargs)
    return wrapper


def superuser_required(view_func):
    """Como staff_required, pero solo para superusuarios (consola SQL: ve toda la base de datos)."""
    @staff_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return view_func(request, *args, **kwargs)
    return wrapper
