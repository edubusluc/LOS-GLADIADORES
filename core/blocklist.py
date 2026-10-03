"""
Emails bloqueados por el personal de Zyra (core.models.BlockedEmail).

Un email bloqueado no puede registrarse, crear un club, recibir una invitación ni
aceptarla. Para que no se pueda esquivar con variantes del mismo buzón, se compara
normalizado: en minúsculas, sin la parte "+etiqueta" y, en Gmail, sin puntos
(J.Perez+club@Gmail.com = jperez@gmail.com). Cada comprobación es una sola consulta
por igualdad sobre un campo único (con índice), así que no se ralentiza aunque la
lista tenga cientos de miles de emails.

Además se guarda la cuenta a la que pertenecía el email: así cambiar el email de la
cuenta (en allauth o desde el club) no sirve para saltarse el bloqueo.
"""
from django.db.models import Q

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


def normalize_email(email):
    """
    Forma normalizada del email: en minúsculas, sin "+etiqueta" y, en Gmail, sin
    puntos y con el dominio gmail.com.
    """
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def is_blocked(email):
    """True si el email (normalizado) está bloqueado."""
    from .models import BlockedEmail

    normalized = normalize_email(email)
    return bool(normalized) and BlockedEmail.objects.filter(email=normalized).exists()


def is_user_blocked(user):
    """La cuenta está bloqueada: por su email actual o porque se bloqueó con otro email suyo."""
    from .models import BlockedEmail

    if not user or not user.is_authenticated:
        return False
    condition = Q(user=user)
    normalized = normalize_email(user.email)
    if normalized:
        condition |= Q(email=normalized)
    return BlockedEmail.objects.filter(condition).exists()


def block(email, *, user=None, club=None, reason="", blocked_by=None):
    """
    Bloquea el email (si ya lo estaba, no hace nada) y la cuenta ``user`` (por defecto,
    la que tiene ese email). Devuelve True si es nuevo.
    """
    from django.contrib.auth import get_user_model

    from .models import BlockedEmail

    normalized = normalize_email(email)
    if not normalized:
        return False
    if user is None:
        user = get_user_model().objects.filter(email__iexact=email.strip()).first()
    blocked, created = BlockedEmail.objects.get_or_create(email=normalized, defaults={
        "original_email": email.strip(), "user": user, "club": club, "reason": reason[:500], "blocked_by": blocked_by,
    })
    if not created and user and blocked.user_id is None:
        blocked.user = user
        blocked.save(update_fields=["user"])
    return created


def unblock_club(club):
    """
    Al reactivar un club se desbloquean los emails que se bloquearon al suspenderlo, salvo
    los de quien también es miembro de otro club suspendido: esos pasan a ese club.
    Devuelve cuántos se han desbloqueado.
    """
    from .models import BlockedEmail, Membership

    unblocked = 0
    for blocked in BlockedEmail.objects.filter(club=club):
        other = None
        if blocked.user_id:
            other = (Membership.objects.filter(user_id=blocked.user_id, club__suspended_at__isnull=False)
                     .exclude(club=club).values_list("club_id", flat=True).first())
        if other:
            blocked.club_id = other
            blocked.save(update_fields=["club"])
        else:
            blocked.delete()
            unblocked += 1
    return unblocked
