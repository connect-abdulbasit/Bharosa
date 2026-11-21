"""Public API access: a JWT *or* an X-API-Key. Keys are scoped, hashed at rest, revocable; every use is audited
and updates last_used_at. Keys can only reach the read-only /public routes (everything else needs a JWT)."""
import hashlib
from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import SAFE_METHODS, bearer, get_current_user
from app.db import get_db
from app.models import ApiKey, User
from app.models.base import utcnow
from app.services import audit
from contracts.enums import Role

KEY_SCOPES = ("cases:read", "messages:check")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, scheme_name="ApiKeyAuth",
                              description="Partner API key created by an admin (`POST /apikeys`). Scopes: cases:read, messages:check. "
                                          "Only the /public routes accept it.")


@dataclass
class Principal:
    kind: str  # "user" | "apikey"
    id: str
    user: Optional[User] = None
    key: Optional[ApiKey] = None


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _deny(db: Session, request: Request, reason: str, status: int, raw: str, key: Optional[ApiKey] = None) -> HTTPException:
    audit.log(db, "system", key.id if key else None, "apikey.denied", "api_key", key.id if key else None,
              after={"reason": reason, "prefix": raw[:13], "path": request.url.path, "method": request.method})
    db.commit()
    return HTTPException(status_code=status, detail={401: "Invalid or revoked API key", 403: "This API key does not have the '%s' scope" % reason}.get(status, reason))


def authenticate_key(db: Session, request: Request, raw: str, scope: str) -> ApiKey:
    key = db.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw))).scalar_one_or_none()
    if key is None or not key.active:
        raise _deny(db, request, "unknown or revoked", 401, raw, key)
    if scope not in (key.scopes or []):
        raise _deny(db, request, scope, 403, raw, key)
    key.last_used_at = utcnow()
    audit.log(db, "system", key.id, "apikey.use", "api_key", key.id,
              after={"name": key.name, "scope": scope, "path": request.url.path, "method": request.method, "owner_id": key.owner_id})
    db.commit()
    return key


def public_access(scope: str) -> Callable[..., Principal]:
    """Dependency for /public routes: X-API-Key with `scope`, or a normal JWT (then the usual role/row rules apply)."""

    def dependency(request: Request, x_api_key: Optional[str] = Security(api_key_header),
                   creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer), db: Session = Depends(get_db)) -> Principal:
        if x_api_key:
            key = authenticate_key(db, request, x_api_key, scope)
            request.state.role = "apikey"
            return Principal("apikey", key.id, key=key)
        user = get_current_user(request, creds, db)  # 401 when there is no valid JWT either
        if user.role == Role.auditor.value and request.method not in SAFE_METHODS:
            raise HTTPException(status_code=403, detail="Auditors are read-only")
        return Principal("user", user.id, user=user)

    return dependency


__all__ = ["KEY_SCOPES", "Principal", "api_key_header", "authenticate_key", "hash_key", "public_access"]
