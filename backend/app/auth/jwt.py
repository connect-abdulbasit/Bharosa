import time
from typing import Any, Dict

import jwt

from app.config import settings


def create_token(user_id: str, role: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + settings.JWT_EXPIRES_SECONDS}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """Raises jwt.PyJWTError on any invalid/expired token."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
