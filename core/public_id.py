"""
Identificadores públicos al estilo Salesforce.

Cada objeto tiene, además de su id numérico interno (la clave primaria, que siguen
usando las relaciones), un ``public_id`` de 15 caracteres: un prefijo de 3 letras
que dice qué tipo de objeto es y 12 caracteres aleatorios. Es el que aparece en las
URLs, así no se ven números consecutivos (``/players/player_details/PLYa8Kd02LmQx7Z/``
en vez de ``/players/player_details/2/``).

Los objetos nuevos lo reciben al guardarse. Para las filas que ya existían:
``python manage.py assign_public_ids``.
"""
import secrets
import string

from django.db import models
from django.db.models.signals import class_prepared

ALPHABET = string.ascii_letters + string.digits
PREFIX_LENGTH = 3
RANDOM_LENGTH = 12
LENGTH = PREFIX_LENGTH + RANDOM_LENGTH

# Prefijo -> "app_label.Model". Se rellena al definir cada modelo; evita prefijos repetidos.
PREFIXES = {}


def new_public_id(prefix):
    """Identificador público nuevo: ``prefix`` y 12 caracteres aleatorios."""
    return prefix + "".join(secrets.choice(ALPHABET) for _ in range(RANDOM_LENGTH))


class PublicIdQuerySet(models.QuerySet):
    """QuerySet que asigna el public_id también en bulk_create."""
    def bulk_create(self, objs, *args, **kwargs):
        """bulk_create no llama a save(): se asigna aquí el identificador."""
        objs = list(objs)
        for obj in objs:
            if not obj.public_id:
                obj.assign_public_id()
        return super().bulk_create(objs, *args, **kwargs)


class PublicIdModel(models.Model):
    """Modelo abstracto: añade ``public_id`` y lo asigna al guardar. Cada modelo define PUBLIC_ID_PREFIX."""
    PUBLIC_ID_PREFIX = None

    # null=True para poder añadir la columna a tablas con datos; las filas existentes
    # se rellenan con el comando assign_public_ids.
    public_id = models.CharField(max_length=LENGTH, unique=True, null=True, blank=True, editable=False)

    objects = PublicIdQuerySet.as_manager()

    class Meta:
        abstract = True

    def assign_public_id(self):
        """Genera y asigna un public_id nuevo con el prefijo del modelo; lo devuelve."""
        # 62^12 combinaciones: una colisión es prácticamente imposible y, si la hubiera,
        # la restricción unique de la base de datos la rechaza.
        self.public_id = new_public_id(self.PUBLIC_ID_PREFIX)
        return self.public_id

    def save(self, *args, **kwargs):
        """Asigna el public_id si no lo tiene (también con ``update_fields``) y guarda."""
        if not self.public_id:
            self.assign_public_id()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = {*update_fields, "public_id"}
        super().save(*args, **kwargs)


def _check_prefix(sender, **kwargs):
    """
    Señal class_prepared: comprueba que cada modelo con public_id tiene un prefijo de 3
    letras o números y que no lo usa otro modelo.
    """
    if not issubclass(sender, PublicIdModel) or sender._meta.abstract:
        return
    prefix, label = sender.PUBLIC_ID_PREFIX, sender._meta.label
    if not prefix or len(prefix) != PREFIX_LENGTH or any(c not in ALPHABET for c in prefix):
        raise ValueError(f"{label}.PUBLIC_ID_PREFIX debe tener {PREFIX_LENGTH} letras o números.")
    if PREFIXES.setdefault(prefix, label) != label:
        raise ValueError(f"El prefijo {prefix!r} de {label} ya lo usa {PREFIXES[prefix]}.")


class_prepared.connect(_check_prefix)


def public_id_models():
    """Todos los modelos instalados que tienen public_id."""
    from django.apps import apps
    return [m for m in apps.get_models() if issubclass(m, PublicIdModel)]


class PublicIdConverter:
    """Conversor de URL ``<pid:...>``: solo acepta identificadores públicos bien formados."""
    regex = f"[A-Za-z0-9]{{{LENGTH}}}"

    def to_python(self, value):
        """Devuelve el identificador tal cual (las vistas buscan por public_id)."""
        return value

    def to_url(self, value):
        """Devuelve el identificador tal cual para construir la URL."""
        return value
