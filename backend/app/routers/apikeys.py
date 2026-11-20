import hashlib
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import ApiKey, User
from app.services import audit
from app.services.serialize import iso
from contracts.enums import Role
from contracts.schemas import ApiKeyCreate, ApiKeyListResponse, ApiKeyRecord

router = APIRouter(tags=["apikeys"])


class ApiKeyCreated(ApiKeyRecord):
    key: str  # shown ONCE; only a sha256 hash is stored


def _out(k: ApiKey) -> dict:
    return {"id": k.id, "name": k.name, "prefix": k.prefix, "scopes": list(k.scopes or []), "created_at": iso(k.created_at),
            "last_used_at": iso(k.last_used_at), "revoked": not k.active}


@router.get("/apikeys", response_model=ApiKeyListResponse)
def list_keys(user=Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    return {"items": [_out(k) for k in db.execute(select(ApiKey).order_by(ApiKey.created_at.desc())).scalars()]}


@router.post("/apikeys", response_model=ApiKeyCreated)
def create_key(body: ApiKeyCreate, user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    # TODO(Basit): authenticate requests with X-API-Key + scopes, per-key rate limiting.
    raw = "bhr_live_" + secrets.token_urlsafe(24)
    k = ApiKey(name=body.name, key_hash=hashlib.sha256(raw.encode()).hexdigest(), prefix=raw[:13], owner_id=user.id, scopes=body.scopes)
    db.add(k)
    db.flush()
    audit.log(db, "user", user.id, "apikey.create", "api_key", k.id, after={"name": k.name, "scopes": k.scopes})
    db.commit()
    return dict(_out(k), key=raw)


