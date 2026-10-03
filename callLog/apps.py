"""Configuración de la aplicación del registro de convocatorias."""
from django.apps import AppConfig


class CalllogConfig(AppConfig):
    """Aplicación del registro de convocatorias."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'callLog'
