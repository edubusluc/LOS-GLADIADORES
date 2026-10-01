import datetime

from django import template
from django.utils import timezone
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def ago(value):
    """'ahora mismo' si fue hace menos de un minuto; si no, 'hace 5 minutos'."""
    if not value:
        return "nunca"
    if not isinstance(value, datetime.datetime):  # una fecha sin hora
        if value >= timezone.localdate():
            return "hoy"
        return f"hace {timesince(value)}"
    if (timezone.now() - value).total_seconds() < 60:
        return "ahora mismo"
    return f"hace {timesince(value)}"


@register.filter
def duration(value):
    """Duración legible de un timedelta: '0,4 s', '12 s', '3 min 5 s'."""
    if value is None:
        return "—"
    seconds = value.total_seconds()
    if seconds < 10:
        return f"{seconds:.1f} s".replace(".", ",")
    if seconds < 60:
        return f"{int(seconds)} s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"


@register.filter
def cron_text(job):
    """Horario de un proceso en palabras ('Cada día a las 03:00')."""
    from backoffice.cron import Cron
    spec = getattr(job, "spec", None)
    if spec is None:
        return "—"
    return Cron(spec.schedule).describe() if spec.schedule else "Solo a mano"


@register.inclusion_tag("backoffice/includes/run_status.html")
def run_status(run):
    return {"run": run}
