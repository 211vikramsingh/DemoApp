"""
Password hashing, JWT creation/verification, and AES-256 API key encryption.
Credentials are NEVER stored or logged in plaintext.
"""
import base64
import os
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    """Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


# ── AES-256-GCM encryption for broker API secrets ────────────────────────────
#
# Encrypted format (base64-encoded):
#   byte 0       : version (currently 0x01)
#   bytes 1-12   : random 96-bit nonce
#   bytes 13+    : AES-256-GCM ciphertext + 16-byte auth tag
#
# Version byte allows future key rotation: decrypt old blobs with old key,
# re-encrypt with new key, bump version byte.

_CURRENT_VERSION = b"\x01"


def _get_aes_key() -> bytes:
    """
    Derive a 32-byte AES key from the hex-encoded ENCRYPTION_KEY env var.
    Raises ValueError at startup if the key is misconfigured rather than
    silently degrading entropy (e.g. via null-byte padding).
    """
    raw = settings.encryption_key
    if raw in ("CHANGE_ME_32_BYTE_HEX", ""):
        raise ValueError(
            "ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    try:
        key_bytes = bytes.fromhex(raw)
    except ValueError:
        raise ValueError(
            "ENCRYPTION_KEY must be a 64-character hex string (32 bytes). "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if len(key_bytes) != 32:
        raise ValueError(
            f"ENCRYPTION_KEY decoded to {len(key_bytes)} bytes; exactly 32 required."
        )
    return key_bytes


def encrypt_secret(plaintext: str) -> str:
    """
    Encrypt a broker secret with AES-256-GCM.
    Returns base64-encoded blob: version(1) + nonce(12) + ciphertext+tag.
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(_CURRENT_VERSION + nonce + ct).decode()


def decrypt_secret(encoded: str) -> str:
    """
    Decrypt a previously encrypted broker secret.
    Validates the version byte to detect key rotation mismatches.
    Raises ValueError if decryption fails (wrong key, corrupted data).
    """
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError(f"Invalid base64 in encrypted secret: {exc}") from exc

    if len(raw) < 14:  # 1 version + 12 nonce + at least 1 byte ciphertext
        raise ValueError("Encrypted secret is too short — data may be corrupted")

    version, nonce, ct = raw[0:1], raw[1:13], raw[13:]
    if version != _CURRENT_VERSION:
        raise ValueError(
            f"Encrypted secret version {version!r} does not match current version "
            f"{_CURRENT_VERSION!r}. Re-encrypt with the current key."
        )

    try:
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception as exc:
        raise ValueError(
            "AES-GCM decryption failed — wrong ENCRYPTION_KEY or corrupted ciphertext"
        ) from exc
