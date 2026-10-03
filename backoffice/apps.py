"""Configuración de la aplicación del back-office."""
from django.apps import AppConfig


class BackofficeConfig(AppConfig):
    """Aplicación del back-office del personal de Zyra."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "backoffice"
    verbose_name = "Back-office"

    def ready(self):
        """Conecta las señales del back-office."""
        from . import signals  # noqa: F401
