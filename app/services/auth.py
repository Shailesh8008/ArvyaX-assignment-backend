import hashlib
import hmac
import secrets
from datetime import datetime, timezone


PASSWORD_SALT_BYTES = 16
PASSWORD_ITERATIONS = 100_000
SESSION_TOKEN_BYTES = 32


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"{salt.hex()}:{derived_key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, derived_key_hex = password_hash.split(":", maxsplit=1)
    except ValueError:
        return False

    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(derived_key_hex)
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return hmac.compare_digest(candidate, expected)


def create_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
