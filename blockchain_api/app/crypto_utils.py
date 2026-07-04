"""
Шифрование приватных ключей (Fernet — симметричное шифрование AES-128)
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    """Создаёт Fernet-ключ из SECRET_KEY приложения."""
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_private_key(private_key: str) -> str:
    """Шифрует приватный ключ перед сохранением в БД."""
    f = _get_fernet()
    return f.encrypt(private_key.encode()).decode()


def decrypt_private_key(encrypted_key: str) -> str:
    """Расшифровывает приватный ключ из БД."""
    f = _get_fernet()
    return f.decrypt(encrypted_key.encode()).decode()
