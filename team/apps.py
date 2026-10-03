"""Configuración de la aplicación de equipos."""
from django.apps import AppConfig


class TeamConfig(AppConfig):
    """Aplicación de equipos."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'team'
