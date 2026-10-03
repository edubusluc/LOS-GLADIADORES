"""Configuración de la app ``match``."""
from django.apps import AppConfig


class MatchConfig(AppConfig):
    """Configuración de la app de partidos."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'match'
