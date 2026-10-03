"""
Emails bloqueados por el personal de Zyra (core.models.BlockedEmail).

Un email bloqueado no puede registrarse, crear un club, recibir una invitación ni
aceptarla. Para que no se pueda esquivar con variantes del mismo buzón, se compara
normalizado: en minúsculas, sin la parte "+etiqueta" y, en Gmail, sin puntos
(J.Perez+club@Gmail.com = jperez@gmail.com). Cada comprobación es una sola consulta
por igualdad sobre un campo único (con índice), así que no se ralentiza aunque la
lista tenga cientos de miles de emails.
"""
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(email):
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def is_blocked(email):
    from .models import BlockedEmail

    normalized = normalize_email(email)
    return bool(normalized) and BlockedEmail.objects.filter(email=normalized).exists()


def block(email, *, club=None, reason="", blocked_by=None):
    """Bloquea el email (si ya lo estaba, no hace nada). Devuelve True si es nuevo."""
    from .models import BlockedEmail

    normalized = normalize_email(email)
    if not normalized:
        return False
    _, created = BlockedEmail.objects.get_or_create(email=normalized, defaults={
        "original_email": email.strip(), "club": club, "reason": reason[:500], "blocked_by": blocked_by,
    })
    return created
