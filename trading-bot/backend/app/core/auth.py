"""
TOTP-based 2FA helpers using pyotp.
Each user's TOTP secret is stored AES-256-GCM encrypted in the database.
"""
import pyotp

from app.core.security import decrypt_secret, encrypt_secret


def generate_totp_secret() -> str:
    """Generate a new random TOTP secret (base32)."""
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: str = "TradingBot") -> str:
    """Return the otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(encrypted_secret: str, code: str) -> bool:
    """
    Verify a TOTP code against the user's encrypted secret.
    Accepts codes valid within a ±30-second window.
    """
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def encrypt_totp_secret(secret: str) -> str:
    return encrypt_secret(secret)
