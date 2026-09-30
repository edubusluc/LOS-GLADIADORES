"""Envío del informe de convocatoria a los administradores del club."""
import logging

from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import format_html

from core.models import Membership

from .report import build_report
from .report_pdf import render_report

logger = logging.getLogger(__name__)


def report_filename(match):
    return f"convocatoria-{match.start_date:%Y%m%d}-{match.local}-vs-{match.visiting}.pdf".replace(" ", "_")


def admin_emails(club):
    return sorted({
        m.user.email for m in Membership.objects.filter(club=club, role=Membership.ADMIN).select_related("user")
        if m.user.email and m.user.is_active
    })


def _bodies(match):
    """Texto plano y HTML del correo. Un cuerpo con algo de contexto y versión HTML
    se parece más a un correo escrito por una persona y ayuda a no caer en spam."""
    rival = match.visiting if match.own_is_local else match.local
    date = f"{match.start_date:%d/%m/%Y}"
    club = match.club.name
    text = (
        f"Hola,\n\n"
        f"Se ha cerrado la convocatoria de {club} para el partido contra {rival} del {date} "
        f"({match.local} vs {match.visiting}).\n\n"
        f"Te adjuntamos el informe en PDF con el estado del equipo, las rachas, los precedentes "
        f"contra este rival y dos alineaciones recomendadas según el formato de la SNP.\n\n"
        f"Si tienes cualquier duda, responde a este correo y le llegará a quien cerró la convocatoria.\n\n"
        f"Un saludo,\nZyra · {club}"
    )
    html = format_html(
        "<p>Hola,</p>"
        "<p>Se ha cerrado la convocatoria de <strong>{}</strong> para el partido contra "
        "<strong>{}</strong> del <strong>{}</strong> ({} vs {}).</p>"
        "<p>Te adjuntamos el informe en PDF con el estado del equipo, las rachas, los precedentes "
        "contra este rival y dos alineaciones recomendadas según el formato de la SNP.</p>"
        "<p>Si tienes cualquier duda, responde a este correo y le llegará a quien cerró la convocatoria.</p>"
        "<p>Un saludo,<br>Zyra · {}</p>",
        club, rival, date, match.local, match.visiting, club,
    )
    return text, html


def send_call_report(call, sender=None):
    """
    Genera el PDF y lo envía a los administradores del club con email.
    Se manda un correo individual a cada administrador (nadie ve las direcciones
    de los demás) y, si se indica quién cerró la convocatoria (``sender``) y tiene
    email, las respuestas le llegan a esa persona (Reply-To).
    Devuelve la lista de destinatarios (vacía si ningún administrador tiene email).
    """
    match = call.match
    recipients = admin_emails(match.club)
    if not recipients:
        return []

    pdf = render_report(build_report(call))
    subject = f"Convocatoria cerrada · {match.local} vs {match.visiting} ({match.start_date:%d/%m/%Y})"
    text, html = _bodies(match)
    reply_to = [sender.email] if sender is not None and sender.email else None

    messages = []
    for recipient in recipients:
        email = EmailMultiAlternatives(subject=subject, body=text, to=[recipient], reply_to=reply_to)
        email.attach_alternative(html, "text/html")
        email.attach(report_filename(match), pdf, "application/pdf")
        messages.append(email)
    get_connection(fail_silently=False).send_messages(messages)
    logger.info("Informe de convocatoria %s enviado a %s", call.pk, recipients)
    return recipients
