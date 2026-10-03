"""Configuración de la aplicación de advertencias."""
from django.apps import AppConfig


class PenaltyConfig(AppConfig):
    """Aplicación de advertencias."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'penalty'
