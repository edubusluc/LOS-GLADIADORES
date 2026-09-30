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
