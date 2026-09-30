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


class ScheduledJob(models.Model):
    """
    Estado de un proceso programado. La definición (comando, horario) está en
    backoffice/jobs.py; esta fila se crea sola la primera vez que se ve el proceso.
    """
    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField("activo", default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    # Marca de "en ejecución", para que el mismo proceso no se lance dos veces a la vez.
    running_since = models.DateTimeField(null=True, blank=True)
    # "Ejecutar ahora" desde el back-office: lo recoge el lanzador en su siguiente pasada.
    run_requested_at = models.DateTimeField(null=True, blank=True)
    run_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "proceso programado"
        verbose_name_plural = "procesos programados"

    @property
    def spec(self):
        from .jobs import get_spec
        return get_spec(self.name)

    def __str__(self):
        return self.name


class JobRun(models.Model):
    """Una ejecución de un proceso programado, con su salida y, si falló, el error."""
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    STATUSES = [(RUNNING, "En curso"), (OK, "Correcta"), (ERROR, "Con error")]

    SCHEDULE = "schedule"
    MANUAL = "manual"
    TRIGGERS = [(SCHEDULE, "Programada"), (MANUAL, "Manual")]

    job = models.ForeignKey(ScheduledJob, on_delete=models.CASCADE, related_name="runs")
    trigger = models.CharField(max_length=10, choices=TRIGGERS, default=SCHEDULE)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    status = models.CharField(max_length=10, choices=STATUSES, default=RUNNING, db_index=True)
    started_at = models.DateTimeField(db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    output = models.TextField(blank=True, default="")
    error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "ejecución de proceso"
        verbose_name_plural = "ejecuciones de procesos"

    @property
    def duration(self):
        if self.finished_at:
            return self.finished_at - self.started_at
        return None

    def __str__(self):
        return f"{self.job} {self.started_at:%Y-%m-%d %H:%M} ({self.get_status_display()})"


class SavedQuery(models.Model):
    """Consulta SQL guardada en la consola, para repetirla o exportarla cuando haga falta."""
    name = models.CharField("nombre", max_length=120, unique=True)
    description = models.CharField("descripción", max_length=255, blank=True, default="")
    sql = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "consulta guardada"
        verbose_name_plural = "consultas guardadas"

    def __str__(self):
        return self.name


class QueryLog(models.Model):
    """Auditoría: cada consulta lanzada o exportada desde la consola SQL."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    sql = models.TextField()
    exported = models.BooleanField("exportada", default=False)
    row_count = models.PositiveIntegerField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "consulta ejecutada"
        verbose_name_plural = "consultas ejecutadas"

    def __str__(self):
        return f"{self.user} {self.created_at:%Y-%m-%d %H:%M}"


class ImportJob(models.Model):
    """Una importación de datos: el fichero, cómo se emparejaron sus columnas y qué cambió."""
    DRAFT = "draft"
    DONE = "done"
    UNDONE = "undone"
    STATUSES = [(DRAFT, "Sin confirmar"), (DONE, "Importada"), (UNDONE, "Deshecha")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    club = models.ForeignKey("core.Club", on_delete=models.CASCADE, related_name="+")
    entity = models.CharField("objeto", max_length=20)
    mode = models.CharField("modo", max_length=10)
    filename = models.CharField(max_length=255)
    content = models.TextField()
    mapping = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=DRAFT)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "importación"
        verbose_name_plural = "importaciones"

    @property
    def entity_spec(self):
        from .importer import ENTITIES
        return ENTITIES.get(self.entity)

    @property
    def mode_label(self):
        from .importer import MODES
        return dict(MODES).get(self.mode, self.mode)

    def __str__(self):
        return f"{self.filename} → {self.entity} ({self.get_status_display()})"
