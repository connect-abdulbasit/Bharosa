import hashlib
import secrets

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.auth.apikey import KEY_SCOPES
from app.db import get_db
from app.models import ApiKey, User
from app.routing import CompactRoute
from app.services import audit
from app.services.serialize import iso
from contracts.enums import Role
from contracts.schemas import ApiKeyCreate, ApiKeyListResponse, ApiKeyRecord

router = APIRouter(tags=["apikeys"], route_class=CompactRoute)


class ApiKeyCreated(ApiKeyRecord):
    key: str  # shown ONCE; only a sha256 hash is stored


def _out(k: ApiKey) -> dict:
    return {"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": list(k.scopes or []), "created_at": iso(k.created_at),
            "last_used_at": iso(k.last_used_at), "revoked": not k.active}


@router.get("/apikeys", response_model=ApiKeyListResponse, summary="List API keys (never shows the key itself)")
def list_keys(user=Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    return {"items": [_out(k) for k in db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars()]}


@router.post("/apikeys", response_model=ApiKeyCreated, summary="Create an API key (shown once)")
def create_key(body: ApiKeyCreate = Body(..., openapi_examples={"ngo": {"summary": "Read-only partner", "value": {"name": "Partner NGO", "scopes": ["cases:read", "messages:check"]}}}),
               user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    """The full key is in this response **only**; we store a hash. Allowed scopes: `cases:read`, `messages:check`.
    Use it as header `X-API-Key: <key>` on the `/public` routes."""
    bad = [s for s in body.scopes if s not in KEY_SCOPES]
    if not body.scopes or bad:
        raise HTTPException(status_code=422, detail="scopes must be a non-empty list of %s%s" % (list(KEY_SCOPES), " (unknown: %s)" % bad if bad else ""))
    raw = "bhr_live_" + secrets.token_urlsafe(24)
    k = ApiKey(name=body.name, key_hash=hashlib.sha256(raw.encode()).hexdigest(), prefix=raw[:13], owner_id=user.id, scopes=sorted(set(body.scopes)))
    db.add(k)
    db.flush()
    audit.log(db, "user", user.id, "apikey.create", "api_key", k.id, after={"name": k.name, "scopes": k.scopes})
    db.commit()
    return dict(_out(k), key=raw)


@router.post("/apikeys/{key_id}/revoke", response_model=ApiKeyRecord, summary="Revoke an API key (immediately)")
def revoke_key(key_id: str, user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    k = db.get(ApiKey, key_id)
    if k is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if not k.active:
        raise HTTPException(status_code=409, detail="API key is already revoked")
    k.active = False
    audit.log(db, "user", user.id, "apikey.revoke", "api_key", k.id, before={"active": True}, after={"active": False})
    db.commit()
    return _out(k)
