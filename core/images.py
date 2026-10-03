"""
Fotos subidas por los usuarios (escudos de equipo y fotos de jugador).

Se guardan con el almacenamiento de Django (settings.STORAGES["default"]): en local, en la
carpeta media/ (MEDIA_ROOT), nunca en static/. Antes de guardarlas se procesan con Pillow:
se comprueba que son una imagen, se giran según la orientación EXIF del móvil, se reducen a
PHOTO_MAX_SIZE píxeles de lado como máximo y se guardan en WebP. Al volver a codificarlas se
pierden los metadatos (EXIF, ubicación GPS...).

Cuando una foto se cambia o se borra su equipo/jugador, el fichero antiguo se borra del
almacenamiento si ya no lo usa nadie más.
"""
import uuid
from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.translation import gettext as _
from PIL import Image, ImageOps

# Carpetas del almacenamiento donde van las fotos. Las rutas que no empiezan por una de
# ellas son antiguas (static/team, static/profile): las mueve el comando move_photos_to_media.
TEAM_PHOTO_DIR = "teams"
PLAYER_PHOTO_DIR = "players"
PHOTO_DIRS = (TEAM_PHOTO_DIR, PLAYER_PHOTO_DIR)


def team_photo_path(instance, filename):
    return _random_name(TEAM_PHOTO_DIR, filename)


def player_photo_path(instance, filename):
    return _random_name(PLAYER_PHOTO_DIR, filename)


def _random_name(folder, filename):
    # Nombre aleatorio: no choca con otras fotos ni deja ver el nombre del fichero original.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webp"
    return f"{folder}/{uuid.uuid4().hex}.{ext}"


def process_image(source):
    """
    Lee una imagen (fichero subido o abierto) y devuelve un ContentFile .webp reducido.
    Lanza ValidationError si no es una imagen válida o es demasiado grande.
    """
    max_bytes = settings.PHOTO_MAX_UPLOAD_MB * 1024 * 1024
    if getattr(source, "size", None) and source.size > max_bytes:
        raise ValidationError(
            _("La imagen ocupa demasiado (máximo %(mb)s MB).") % {"mb": settings.PHOTO_MAX_UPLOAD_MB}
        )
    try:
        source.seek(0)
        with Image.open(source) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            # WebP admite transparencia (escudos PNG); el resto se pasa a RGB.
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            img = img.convert("RGBA" if has_alpha else "RGB")
            img.thumbnail((settings.PHOTO_MAX_SIZE, settings.PHOTO_MAX_SIZE), Image.LANCZOS)
            out = BytesIO()
            img.save(out, format="WEBP", quality=settings.PHOTO_WEBP_QUALITY, method=6)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ValidationError(_("El archivo no es una imagen válida."))
    return ContentFile(out.getvalue(), name="photo.webp")


def clean_photo_field(form, field_name="photo"):
    """clean_<campo> de los formularios: procesa la foto recién subida y deja las demás igual."""
    photo = form.cleaned_data.get(field_name)
    # Solo los ficheros recién subidos traen content_type; una foto ya guardada se deja igual.
    if photo and hasattr(photo, "content_type"):
        return process_image(photo)
    return photo


def _is_used(model, field_name, name, exclude_pk=None):
    return model._default_manager.filter(**{field_name: name}).exclude(pk=exclude_pk).exists()


def _delete_later(storage, model, field_name, name):
    """Borra el fichero tras confirmar la transacción, si es nuestro y nadie más lo usa."""
    if not name or not name.startswith(tuple(f"{d}/" for d in PHOTO_DIRS)):
        return

    def delete():
        if not _is_used(model, field_name, name):
            storage.delete(name)

    transaction.on_commit(delete)


def connect_photo_cleanup(model, field_name="photo"):
    """Conecta las señales que borran la foto antigua al cambiarla o al borrar el objeto."""
    from django.db.models.signals import post_delete, pre_save

    def on_pre_save(sender, instance, update_fields=None, **kwargs):
        if not instance.pk or (update_fields is not None and field_name not in update_fields):
            return
        old = sender._default_manager.filter(pk=instance.pk).values_list(field_name, flat=True).first()
        new = getattr(instance, field_name).name if getattr(instance, field_name) else None
        if old and old != new:
            _delete_later(getattr(instance, field_name).storage, sender, field_name, old)

    def on_post_delete(sender, instance, **kwargs):
        file = getattr(instance, field_name)
        if file:
            _delete_later(file.storage, sender, field_name, file.name)

    pre_save.connect(on_pre_save, sender=model, weak=False, dispatch_uid=f"{model._meta.label}.{field_name}.pre_save")
    post_delete.connect(on_post_delete, sender=model, weak=False, dispatch_uid=f"{model._meta.label}.{field_name}.post_delete")
