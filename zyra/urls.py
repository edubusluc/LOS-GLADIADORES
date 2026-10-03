"""
URL configuration for zyra project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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
