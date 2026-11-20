"""bcrypt password hashing."""
import bcrypt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("ascii"))
    except ValueError:
        return False
