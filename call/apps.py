"""Configuración de la aplicación de convocatorias."""
from django.apps import AppConfig


class CallConfig(AppConfig):
    """Aplicación de convocatorias."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'call'
