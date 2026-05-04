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

def _get_aes_key() -> bytes:
    """Derive a 32-byte key from the hex-encoded encryption_key setting."""
    raw = settings.encryption_key
    key_bytes = bytes.fromhex(raw) if len(raw) == 64 else raw.encode()[:32]
    return key_bytes.ljust(32, b"\x00")


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a broker secret with AES-256-GCM. Returns base64-encoded ciphertext."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_secret(encoded: str) -> str:
    """Decrypt a previously encrypted broker secret."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encoded)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()
