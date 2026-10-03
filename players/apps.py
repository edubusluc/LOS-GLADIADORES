"""Configuración de la aplicación de jugadores."""
from django.apps import AppConfig


class PlayersConfig(AppConfig):
    """Aplicación de jugadores y su integración con SNP."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'players'
