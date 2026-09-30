"""
Cifrado simétrico (Fernet: AES-128-CBC + HMAC-SHA256) para datos sensibles que la
aplicación necesita poder leer después, como las credenciales de SNP de cada club.

La clave sale de la variable de entorno FIELD_ENCRYPTION_KEY (genérala con
``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``).
Si no está definida se deriva de DJANGO_SECRET_KEY, así que cambiar esa clave dejaría
ilegibles los datos cifrados.
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    pass


def _fernet():
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    if not key:
        digest = hashlib.sha256(f"zyra-field-encryption:{settings.SECRET_KEY}".encode()).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("No se ha podido descifrar el dato: ¿ha cambiado la clave de cifrado?") from exc
