"""DL number encryption utilities using Fernet symmetric encryption.

All DL numbers are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256).
The encryption key must be set via the DL_ENCRYPTION_KEY environment variable.
"""

from cryptography.fernet import Fernet, InvalidToken
from decouple import config
from django.core.exceptions import ImproperlyConfigured


def _get_fernet():
    """Get Fernet cipher instance, validating key on first access.

    Returns:
        Fernet: Configured cipher instance

    Raises:
        ImproperlyConfigured: If DL_ENCRYPTION_KEY is not set or invalid
    """
    try:
        key = config('DL_ENCRYPTION_KEY')
    except Exception as e:
        raise ImproperlyConfigured(
            'DL_ENCRYPTION_KEY environment variable is required for DL encryption. '
            'Generate a key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from e

    if not key:
        raise ImproperlyConfigured('DL_ENCRYPTION_KEY cannot be empty')

    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise ImproperlyConfigured(
            f'DL_ENCRYPTION_KEY is invalid. It must be a 44-character base64url-encoded string. Error: {e}'
        ) from e


def encrypt_dl_number(dl_number: str) -> str:
    """Encrypt DL number using Fernet symmetric encryption.

    Args:
        dl_number: Plaintext DL number (already normalized)

    Returns:
        Base64-encoded ciphertext suitable for CharField(256)

    Raises:
        ValueError: If DL_ENCRYPTION_KEY is not set or invalid
        ImproperlyConfigured: If encryption key is missing or malformed
    """
    if not dl_number:
        raise ValueError('DL number cannot be empty')

    fernet = _get_fernet()
    ciphertext = fernet.encrypt(dl_number.encode('utf-8'))
    return ciphertext.decode('utf-8')


def decrypt_dl_number(encrypted_dl: str) -> str:
    """Decrypt DL number.

    Args:
        encrypted_dl: Base64 ciphertext from database

    Returns:
        Plaintext DL number

    Raises:
        ValueError: If ciphertext is invalid or key is wrong
        ImproperlyConfigured: If encryption key is missing or malformed
    """
    if not encrypted_dl:
        raise ValueError('Encrypted DL cannot be empty')

    fernet = _get_fernet()

    try:
        plaintext = fernet.decrypt(encrypted_dl.encode('utf-8'))
        return plaintext.decode('utf-8')
    except InvalidToken as e:
        raise ValueError(
            'Failed to decrypt DL number. The ciphertext may be corrupted or the encryption key may be wrong.'
        ) from e


def normalize_dl_number(dl_number: str) -> str:
    """Normalize DL number: strip whitespace, uppercase, remove spaces/hyphens.

    Args:
        dl_number: User input (e.g. "mh01 20110012345" or "MH01-20110012345")

    Returns:
        Normalized DL (e.g. "MH0120110012345")
    """
    if not dl_number:
        return ''

    # Strip leading/trailing whitespace, convert to uppercase, remove spaces and hyphens
    normalized = dl_number.strip().upper()
    normalized = normalized.replace(' ', '').replace('-', '')
    return normalized


def get_dl_last_four(dl_number: str) -> str:
    """Extract last 4 chars from normalized DL for display.

    Args:
        dl_number: Normalized DL (e.g. "MH0120110012345")

    Returns:
        Last 4 chars (e.g. "2345")
    """
    if not dl_number:
        return ''
    return dl_number[-4:]
