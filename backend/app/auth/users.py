"""Seeded DEMO users, one per role. Fake, prototype only.
TODO(Basit): move to the users table + Alembic seed migration."""
from typing import Dict, Optional

from app.auth.passwords import hash_password
from app.config import settings

_DISPLAY = {
    "citizen": "Fatima Bibi (demo)",
    "helper": "Nasreen Akhtar (demo helper)",
    "officer": "Officer Imran (demo)",
    "admin": "Admin (demo)",
    "auditor": "Auditor (demo)",
}

USERS: Dict[str, dict] = {
    role: {
        "user_id": "u-%s-1" % role,
        "username": role,
        "display_name": _DISPLAY[role],
        "role": role,
        "language": "ur",
        "password_hash": hash_password(pw),
    }
    for role, pw in settings.DEMO_PASSWORDS.items()
}


def get_user_by_username(username: str) -> Optional[dict]:
    return USERS.get(username)


def get_user_by_id(user_id: str) -> Optional[dict]:
    return next((u for u in USERS.values() if u["user_id"] == user_id), None)
