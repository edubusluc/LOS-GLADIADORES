"""
Mapa de URLs del proyecto.

- ADMIN_URL: Django admin (solo superusuarios).
- backoffice/: back-office del personal de Zyra (app backoffice).
- "" (raíz): portada (core.views.home).
- players/: jugadores (app players).
- match/: partidos (app match).
- data_analyse/: estadísticas (app data_analyse).
- team/: equipos (app team).
- callLog/: registro de convocatorias (app callLog).
- penalty/: sanciones (app penalty).
- core/: inicio de sesión, alta de club, miembros e invitaciones (app core).
- accounts/: cuentas de django-allauth (inicio de sesión con Google, contraseñas...).
- i18n/ y jsi18n/: selector de idioma y traducciones para el JavaScript.

En local también sirve las fotos subidas (MEDIA_URL). Registra el conversor ``<pid:...>``
y las vistas de error 403 y 404.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, register_converter
from django.views.i18n import JavaScriptCatalog

from core.public_id import PublicIdConverter

from core.views import error_403_view, error_404_view, home

# <pid:...>: identificador público de un objeto (core/public_id.py). Se registra antes de
# cargar las URLs de cada aplicación, que lo usan.
register_converter(PublicIdConverter, "pid")

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('backoffice/', include('backoffice.urls')),
    path("", home, name="home"),
    path('players/', include('players.urls')),
    path('match/', include('match.urls')),
    path('data_analyse/',include('data_analyse.urls')),
    path('team/',include('team.urls')),
    path('callLog/',include('callLog.urls')),
    path('penalty/',include('penalty.urls')),
    path('core/', include('core.urls')),
    path('accounts/', include('allauth.urls')),
    # Selector de idioma (vista set_language) y traducciones de los textos de static/js.
    path('i18n/', include('django.conf.urls.i18n')),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
]

# Fotos subidas (MEDIA_URL): en local las sirve Django; en producción, el servidor web.
# static() no añade nada si DEBUG está desactivado.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = error_403_view
handler404 = error_404_view
