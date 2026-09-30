"""
Registro de los procesos programados de Zyra.

Cada proceso es un comando de Django (``python manage.py <comando>``). Para añadir
uno: crea el comando y añade aquí una entrada. La hora se interpreta en
SCHEDULER_TIME_ZONE (Madrid). En la base de datos solo se guarda el estado de cada
proceso (activo, última y próxima ejecución); la definición manda siempre el código.
"""
from dataclasses import dataclass, field

SCHEDULER_TIME_ZONE = "Europe/Madrid"


@dataclass(frozen=True)
class JobSpec:
    name: str
    description: str
    command: str
    schedule: str
    args: tuple = field(default_factory=tuple)
    # Si una ejecución lleva más de esto en marcha, se da por interrumpida.
    timeout_minutes: int = 60


JOBS = [
    JobSpec(
        name="purge_request_metrics",
        description="Borra las métricas de carga por minuto de más de 30 días.",
        command="purge_request_metrics",
        args=("--days", "30"),
        schedule="0 3 * * *",
    ),
    JobSpec(
        name="purge_job_runs",
        description="Borra el log de ejecuciones de procesos de más de 90 días.",
        command="purge_job_runs",
        args=("--days", "90"),
        schedule="10 3 * * *",
    ),
    JobSpec(
        name="clear_sessions",
        description="Borra de la base de datos las sesiones de usuario caducadas.",
        command="clearsessions",
        schedule="30 3 * * *",
    ),
    JobSpec(
        name="update_snp_scores",
        description="Descarga de SNP los puntos de los jugadores de cada club con cuenta SNP configurada.",
        command="update_snp_scores",
        # Lunes a las 23:00.
        schedule="0 23 * * 1",
    ),
]


def get_spec(name):
    return next((spec for spec in JOBS if spec.name == name), None)
