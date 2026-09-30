"""
Correos que se envían desde join.zyra@gmail.com.

Todos comparten el mismo diseño: el contenido de cada correo va dentro de
``emails/layout.html``, que añade el pie corporativo con el logo de Zyra y los
datos de contacto. El logo viaja incrustado en el propio correo (Content-ID), así
se ve aunque el cliente de correo bloquee las imágenes remotas.
"""
import logging
from email.mime.image import MIMEImage
from functools import lru_cache

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.message import SafeMIMEMultipart
from django.template.loader import render_to_string

from .models import Membership

logger = logging.getLogger(__name__)

LOGO_CID = "zyra-logo"
LOGO_PATH = settings.BASE_DIR / "static" / "zyra" / "email-logo.png"

TEXT_FOOTER = (
    "\n\n--\n"
    "Zyra · Gestión de equipos de pádel\n"
    "Contacto: {contact}\n"
)


@lru_cache(maxsize=1)
def _logo_bytes():
    return LOGO_PATH.read_bytes()


class ZyraEmail(EmailMultiAlternatives):
    """
    Correo con versión HTML y el logo incrustado.

    La parte HTML y el logo van juntos en un bloque multipart/related, y los
    adjuntos (por ejemplo el PDF de la convocatoria) quedan fuera de él:
    mixed[ related[ alternative[texto, html], logo ], adjuntos ].
    """

    def _create_alternatives(self, msg):
        msg = super()._create_alternatives(msg)
        if not self.alternatives:
            return msg
        related = SafeMIMEMultipart(_subtype="related", encoding=self.encoding or settings.DEFAULT_CHARSET)
        related.attach(msg)
        logo = MIMEImage(_logo_bytes(), _subtype="png")
        logo.add_header("Content-ID", f"<{LOGO_CID}>")
        logo.add_header("Content-Disposition", "inline", filename="zyra.png")
        related.attach(logo)
        return related


def build_email(subject, text, html_content, to, reply_to=None):
    """Monta un correo de Zyra con el pie corporativo en texto plano y en HTML."""
    contact = settings.ZYRA_SENDER
    body = text.rstrip() + TEXT_FOOTER.format(contact=contact)
    html = render_to_string("emails/layout.html", {
        "subject": subject,
        "content": html_content,
        "contact": contact,
        "logo_cid": LOGO_CID,
    })
    email = ZyraEmail(subject=subject, body=body, to=to, reply_to=reply_to)
    email.attach_alternative(html, "text/html")
    return email


def club_admins(club):
    return [
        m.user for m in Membership.objects.filter(club=club, role=Membership.ADMIN)
        .select_related("user").order_by("user__username")
    ]


def send_welcome_email(user, club, created=False, site_url=""):
    """
    Correo de bienvenida al entrar en un club (``created=False``) o al registrar
    uno nuevo (``created=True``). Indica el usuario, el club y sus administradores.
    Si el usuario no tiene email no se envía nada. Un fallo al enviar se registra
    pero no interrumpe el registro. Devuelve True si el correo salió.
    """
    if not user.email:
        return False

    context = {
        "user": user,
        "club": club,
        "created": created,
        "admins": club_admins(club),
        "site_url": site_url,
    }
    subject = (
        f"Bienvenido a Zyra · Has creado {club.name}" if created
        else f"Bienvenido a Zyra · Te has unido a {club.name}"
    )
    email = build_email(
        subject,
        render_to_string("emails/welcome.txt", context),
        render_to_string("emails/welcome.html", context),
        to=[user.email],
    )
    try:
        email.send(fail_silently=False)
    except Exception:  # SMTP caído, credenciales mal configuradas...
        logger.exception("No se pudo enviar el correo de bienvenida a %s", user.email)
        return False
    return True
