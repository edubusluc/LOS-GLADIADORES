"""Configuración de la aplicación de estadísticas."""
from django.apps import AppConfig


class DataAnalyseConfig(AppConfig):
    """Aplicación de estadísticas del equipo, jugadores, parejas y advertencias."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_analyse'
