import threading
import time

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils import timezone

from .models import RequestMetric, UserActivity

# Cada cuánto se guarda la actividad de un mismo usuario.
ACTIVITY_EVERY = 60
# Cada cuánto se vuelcan a la base de datos las métricas acumuladas en memoria.
FLUSH_EVERY = 15
SLOW_MS = 1000

# Ficheros estáticos y subidos no cuentan como carga de la aplicación. (MEDIA_URL vale "/"
# si no está configurado, y eso dejaría fuera todas las peticiones.)
_IGNORED_PREFIXES = tuple(
    p for p in (settings.STATIC_URL, getattr(settings, "MEDIA_URL", ""), "/favicon") if p and p != "/"
)


class _Buffer:
    """Contadores del minuto en curso, en memoria de este proceso, para no escribir en cada petición."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset(None)
        self.flushed_at = time.monotonic()

    def reset(self, minute):
        self.minute = minute
        self.requests = self.errors = self.slow = self.total_ms = self.max_ms = 0

    def add(self, minute, ms, status):
        pending = None
        with self.lock:
            if self.minute is not None and minute != self.minute:
                pending = self._take()
            if self.minute is None:
                self.minute = minute
            self.requests += 1
            self.total_ms += ms
            self.max_ms = max(self.max_ms, ms)
            self.errors += status >= 500
            self.slow += ms >= SLOW_MS
            if pending is None and time.monotonic() - self.flushed_at >= FLUSH_EVERY:
                pending = self._take()
        if pending:
            _save(pending)

    def take(self):
        with self.lock:
            return self._take()

    def _take(self):
        data = None
        if self.minute is not None and self.requests:
            data = dict(minute=self.minute, requests=self.requests, errors=self.errors,
                        slow=self.slow, total_ms=self.total_ms, max_ms=self.max_ms)
        self.reset(None)
        self.flushed_at = time.monotonic()
        return data


_buffer = _Buffer()


def _save(data):
    """Suma los contadores a la fila de su minuto (varios procesos pueden escribir en la misma)."""
    minute = data.pop("minute")
    changes = dict(
        requests=F("requests") + data["requests"], errors=F("errors") + data["errors"],
        slow=F("slow") + data["slow"], total_ms=F("total_ms") + data["total_ms"],
        max_ms=Greatest(F("max_ms"), data["max_ms"]),
    )
    if RequestMetric.objects.filter(minute=minute).update(**changes):
        return
    try:
        with transaction.atomic():
            RequestMetric.objects.create(minute=minute, **data)
    except IntegrityError:
        RequestMetric.objects.filter(minute=minute).update(**changes)


def flush_metrics():
    """Vuelca ya lo acumulado. Lo usan los tests y la página de carga."""
    data = _buffer.take()
    if data:
        _save(data)


def activity_cache_key(user_id):
    return f"backoffice:seen:{user_id}"


class ActivityMiddleware:
    """
    Mide cada petición (tiempo y código de respuesta) y apunta la última actividad del
    usuario. Va al principio de MIDDLEWARE para medir la petición completa.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(_IGNORED_PREFIXES):
            return self.get_response(request)

        start = time.monotonic()
        response = self.get_response(request)
        ms = int((time.monotonic() - start) * 1000)
        now = timezone.now()

        try:
            _buffer.add(now.replace(second=0, microsecond=0), ms, response.status_code)
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and cache.add(activity_cache_key(user.pk), 1, ACTIVITY_EVERY):
                UserActivity.objects.update_or_create(user=user, defaults={
                    "last_seen": now,
                    "last_path": request.path[:200],
                    "club": getattr(request, "club", None),
                })
        except Exception:  # la medición nunca debe romper una página
            pass
        return response
