"""
Cifrado simétrico (Fernet: AES-128-CBC + HMAC-SHA256) para datos sensibles que la
aplicación necesita poder leer después, como las credenciales de SNP de cada club.

La clave sale de la variable de entorno FIELD_ENCRYPTION_KEY (genérala con
``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``).
En producción es obligatoria (zyra/settings.py no arranca sin ella). Solo en
desarrollo, si no está definida, se deriva de DJANGO_SECRET_KEY.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    """El dato no se puede descifrar (normalmente porque ha cambiado la clave)."""
    pass


def _fernet():
    """
    Cifrador Fernet con FIELD_ENCRYPTION_KEY o, si no está definida (solo en desarrollo),
    con una clave derivada de SECRET_KEY.
    """
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        digest = hashlib.sha256(f"zyra-field-encryption:{settings.SECRET_KEY}".encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(value):
    """Cifra un texto y devuelve el token como texto."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token):
    """Descifra un token de encrypt(); lanza DecryptionError si no es válido para la clave actual."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("No se ha podido descifrar el dato: ¿ha cambiado la clave de cifrado?") from exc
