"""
Consola SQL del back-office: consultas de SOLO LECTURA sobre toda la base de datos.

La lectura está garantizada por la propia base de datos, no solo por este código:
- SQLite: la conexión se pone en ``PRAGMA query_only`` mientras dura la consulta.
- PostgreSQL: la consulta va en una transacción ``READ ONLY`` con ``statement_timeout``.
Además solo se admite una sentencia que empiece por SELECT o WITH, con límite de
filas y de tiempo, y los datos sensibles (contraseñas, sesiones, tokens) no se pueden
consultar ni aparecen en los resultados.
"""
import re
import time
from dataclasses import dataclass, field

from django.db import connection, transaction

# Filas que se muestran en pantalla y que se exportan como máximo.
DISPLAY_LIMIT = 500
EXPORT_LIMIT = 50_000
# Tiempo máximo de una consulta.
TIMEOUT_SECONDS = 10

# Tablas que no aparecen en el esquema ni se pueden consultar.
HIDDEN_TABLES = {
    "django_session",
    "socialaccount_socialtoken",
    "socialaccount_socialapp",
    "account_emailconfirmation",
}
# Palabras que no pueden aparecer en la consulta: columnas sensibles y funciones
# peligrosas de SQLite.
BLOCKED_WORDS = HIDDEN_TABLES | {
    "password", "token", "secret", "session_key", "session_data",
    "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
}
# Columnas del resultado cuyo valor se oculta aunque lleguen por un SELECT *.
MASKED_COLUMN = re.compile(r"password|token|secret|session", re.IGNORECASE)
MASK = "••••••"


class QueryError(ValueError):
    pass


@dataclass
class QueryResult:
    columns: list
    rows: list
    truncated: bool
    duration_ms: int
    masked: list = field(default_factory=list)

    @property
    def row_count(self):
        return len(self.rows)


_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)
_STRINGS = re.compile(r"'(?:[^']|'')*'")


def clean(sql):
    """Quita comentarios, espacios y el punto y coma final."""
    sql = _COMMENTS.sub(" ", sql or "").strip()
    return sql[:-1].rstrip() if sql.endswith(";") else sql


def validate(sql):
    """Comprueba que la consulta es una única lectura y que no toca datos sensibles."""
    sql = clean(sql)
    if not sql:
        raise QueryError("Escribe una consulta.")
    # Las comprobaciones se hacen sin el contenido de los textos entre comillas.
    code = _STRINGS.sub("''", sql)
    if ";" in code:
        raise QueryError("Solo se puede ejecutar una consulta cada vez.")
    first = code.split(None, 1)[0].lower()
    if first not in ("select", "with"):
        raise QueryError("Solo se admiten consultas de lectura (SELECT o WITH).")
    words = set(re.findall(r"[a-z_][a-z0-9_]*", code.lower()))
    blocked = sorted(words & BLOCKED_WORDS)
    if blocked:
        raise QueryError(f"Esta consulta usa datos protegidos ({', '.join(blocked)}), que no se pueden consultar desde aquí.")
    return sql


def run(sql, limit=DISPLAY_LIMIT, timeout=TIMEOUT_SECONDS):
    """Ejecuta una consulta de solo lectura y devuelve como mucho `limit` filas."""
    sql = validate(sql)
    start = time.monotonic()
    try:
        if connection.vendor == "sqlite":
            columns, rows, truncated = _run_sqlite(sql, limit, timeout)
        elif connection.vendor == "postgresql":
            columns, rows, truncated = _run_postgres(sql, limit, timeout)
        else:
            raise QueryError(f"La consola SQL no está preparada para {connection.vendor}.")
    except QueryError:
        raise
    except Exception as exc:  # error de sintaxis, tabla inexistente, tiempo agotado...
        raise QueryError(_explain(exc, timeout)) from exc
    duration_ms = int((time.monotonic() - start) * 1000)

    masked = [i for i, name in enumerate(columns) if MASKED_COLUMN.search(name or "")]
    if masked:
        rows = [tuple(MASK if i in masked else v for i, v in enumerate(row)) for row in rows]
    return QueryResult(columns, rows, truncated, duration_ms, [columns[i] for i in masked])


def _fetch(cursor, limit):
    columns = [c[0] for c in cursor.description or []]
    rows = cursor.fetchmany(limit + 1)
    return columns, [tuple(r) for r in rows[:limit]], len(rows) > limit


def _run_sqlite(sql, limit, timeout):
    connection.ensure_connection()
    raw = connection.connection
    deadline = time.monotonic() + timeout
    # El manejador de progreso corta la consulta si pasa del tiempo máximo.
    raw.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA query_only = ON")
            try:
                cursor.execute(sql)
                return _fetch(cursor, limit)
            finally:
                cursor.execute("PRAGMA query_only = OFF")
    finally:
        raw.set_progress_handler(None, 0)


def _run_postgres(sql, limit, timeout):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = %s", [int(timeout * 1000)])
        cursor.execute(sql)
        return _fetch(cursor, limit)


def _explain(exc, timeout):
    text = str(exc)
    if "interrupted" in text.lower() or "statement timeout" in text.lower():
        return f"La consulta tardó más de {timeout} segundos y se ha cancelado."
    if "readonly" in text.lower() or "read-only" in text.lower() or "query_only" in text.lower():
        return "La consola es de solo lectura."
    return f"Error en la consulta: {text}"


def schema():
    """Tablas y columnas visibles, para la ayuda lateral de la consola."""
    tables = []
    with connection.cursor() as cursor:
        for name in sorted(connection.introspection.table_names(cursor)):
            if name in HIDDEN_TABLES:
                continue
            columns = [
                col.name for col in connection.introspection.get_table_description(cursor, name)
                if not MASKED_COLUMN.search(col.name)
            ]
            tables.append({"name": name, "columns": columns})
    return tables
