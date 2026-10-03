"""
Validación automática de las fotos subidas con AWS Rekognition (DetectModerationLabels).

Es opcional y está desactivada por defecto (REKOGNITION_ENABLED=False): la revisión
principal la hace el personal en el back-office (Fotos), que elimina las fotos que no
cumplen los términos y avisa al usuario por email.

Solo se usa el plan gratuito de AWS: como mucho REKOGNITION_MONTHLY_LIMIT fotos al mes
(1.000 en el plan gratuito) y solo hasta REKOGNITION_FREE_UNTIL (fin del periodo gratuito
de la cuenta de AWS). Fuera de eso, o si Rekognition no está configurado o falla, la foto
se acepta "sin validar" y queda registrada (core.models.PhotoCheck) para que el personal la
revise en el back-office.

Se rechazan las fotos con alguna etiqueta (o categoría superior) de REKOGNITION_BLOCKED_LABELS
con una confianza mínima de REKOGNITION_MIN_CONFIDENCE.
"""
import logging
from dataclasses import dataclass, field
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class Moderation:
    status: str  # PhotoCheck.APPROVED / REJECTED / UNCHECKED
    reason: str = ""
    api_called: bool = False
    labels: list = field(default_factory=list)


def is_configured():
    return bool(settings.REKOGNITION_ACCESS_KEY_ID and settings.REKOGNITION_SECRET_ACCESS_KEY)


def calls_this_month():
    from .models import PhotoCheck

    start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return PhotoCheck.objects.filter(api_called=True, created_at__gte=start).count()


def free_tier_status():
    """None si se puede llamar a Rekognition gratis; si no, el motivo."""
    if not settings.REKOGNITION_ENABLED:
        return "Rekognition desactivado (REKOGNITION_ENABLED)"
    if not is_configured():
        return "Rekognition no está configurado"
    free_until = settings.REKOGNITION_FREE_UNTIL
    if not free_until:
        return "Falta REKOGNITION_FREE_UNTIL (fin del periodo gratuito)"
    if timezone.localdate() > free_until:
        return f"Periodo gratuito terminado el {free_until:%d/%m/%Y}"
    if calls_this_month() >= settings.REKOGNITION_MONTHLY_LIMIT:
        return f"Límite gratuito del mes alcanzado ({settings.REKOGNITION_MONTHLY_LIMIT} fotos)"
    return None


def _client():
    import boto3

    return boto3.client(
        "rekognition",
        region_name=settings.REKOGNITION_REGION,
        aws_access_key_id=settings.REKOGNITION_ACCESS_KEY_ID,
        aws_secret_access_key=settings.REKOGNITION_SECRET_ACCESS_KEY,
    )


def _jpeg_bytes(content):
    """Rekognition solo admite JPEG y PNG: se envía una copia JPEG de la foto ya procesada."""
    content.seek(0)
    with Image.open(content) as img:
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.getchannel("A"))
        out = BytesIO()
        background.save(out, format="JPEG", quality=90)
    content.seek(0)
    return out.getvalue()


def moderate(content):
    """Valida la foto (ContentFile ya procesado por core.images.process_image)."""
    from .models import PhotoCheck

    blocked_reason = free_tier_status()
    if blocked_reason:
        return Moderation(PhotoCheck.UNCHECKED, blocked_reason)
    try:
        response = _client().detect_moderation_labels(
            Image={"Bytes": _jpeg_bytes(content)}, MinConfidence=settings.REKOGNITION_MIN_CONFIDENCE,
        )
    except Exception as exc:  # red, credenciales, cuota... la foto se acepta sin validar
        logger.warning("Rekognition no ha podido validar una foto: %s", exc)
        return Moderation(PhotoCheck.UNCHECKED, f"Error de Rekognition: {exc}"[:500], api_called=True)

    blocked = {label.lower() for label in settings.REKOGNITION_BLOCKED_LABELS}
    found = []
    for label in response.get("ModerationLabels", []):
        names = {label.get("Name", ""), label.get("ParentName", "")}
        if {n.lower() for n in names if n} & blocked:
            found.append(f"{label['Name']} ({label.get('Confidence', 0):.0f}%)")
    if found:
        return Moderation(PhotoCheck.REJECTED, ", ".join(found)[:500], api_called=True, labels=found)
    return Moderation(PhotoCheck.APPROVED, api_called=True)
