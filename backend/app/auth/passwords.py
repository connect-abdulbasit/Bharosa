"""Password hashing with stdlib PBKDF2 (no extra deps)."""
import hashlib
import hmac
import os
from typing import Optional

ITERATIONS = 120_000


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2$%s$%s" % (salt.hex(), digest.hex())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), ITERATIONS)
    return hmac.compare_digest(candidate.hex(), digest_hex)
