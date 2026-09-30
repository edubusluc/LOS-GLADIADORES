from django.conf import settings
from django.db import models


class UserActivity(models.Model):
    """
    Última vez que cada usuario hizo una petición. Se actualiza como mucho una vez por
    minuto y por usuario (ver ActivityMiddleware) y se borra al cerrar sesión.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity")
    club = models.ForeignKey("core.Club", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    last_seen = models.DateTimeField(db_index=True)
    last_path = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        verbose_name = "actividad de usuario"
        verbose_name_plural = "actividad de usuarios"

    def __str__(self):
        return f"{self.user} ({self.last_seen:%Y-%m-%d %H:%M})"


class RequestMetric(models.Model):
    """Peticiones atendidas por la web, agregadas por minuto."""
    minute = models.DateTimeField(unique=True)
    requests = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField("errores 5xx", default=0)
    slow = models.PositiveIntegerField("lentas (más de 1 s)", default=0)
    total_ms = models.PositiveBigIntegerField(default=0)
    max_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-minute"]
        verbose_name = "métrica de peticiones"
        verbose_name_plural = "métricas de peticiones"

    @property
    def avg_ms(self):
        return round(self.total_ms / self.requests) if self.requests else 0

    def __str__(self):
        return f"{self.minute:%Y-%m-%d %H:%M}: {self.requests}"
