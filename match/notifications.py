"""Envío del informe de convocatoria a los administradores del club."""
import logging

from django.core.mail import EmailMessage

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


def send_call_report(call):
    """
    Genera el PDF y lo envía a los administradores del club con email.
    Devuelve la lista de destinatarios (vacía si ningún administrador tiene email).
    """
    match = call.match
    recipients = admin_emails(match.club)
    if not recipients:
        return []

    pdf = render_report(build_report(call))
    rival = match.visiting if match.own_is_local else match.local
    email = EmailMessage(
        subject=f"Convocatoria cerrada · {match.local} vs {match.visiting} ({match.start_date:%d/%m/%Y})",
        body=(
            f"Se ha cerrado la convocatoria del partido contra {rival} del {match.start_date:%d/%m/%Y}.\n\n"
            f"Adjuntamos el informe con el estado del equipo, las rachas, los precedentes y dos "
            f"alineaciones recomendadas según el formato de la SNP.\n\n— Zyra"
        ),
        to=recipients,
    )
    email.attach(report_filename(match), pdf, "application/pdf")
    email.send(fail_silently=False)
    logger.info("Informe de convocatoria %s enviado a %s", call.pk, recipients)
    return recipients
