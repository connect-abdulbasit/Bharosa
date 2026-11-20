from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import ApiKeyCreate, ApiKeyListResponse, ApiKeyRecord

router = APIRouter(tags=["apikeys"])


@router.get("/apikeys", response_model=ApiKeyListResponse)
def list_keys(user=Depends(require_role(Role.admin))):
    return fixture("apikeys")


@router.post("/apikeys", response_model=ApiKeyRecord)
def create_key(body: ApiKeyCreate, user=Depends(require_role(Role.admin))):
    # TODO(Basit): generate key, show once, store only a hash, add rate limiting per key.
    out = dict(fixture("apikeys")["items"][0], name=body.name, scopes=body.scopes)
    audit.log(user["user_id"], "apikey.create", None, {"name": body.name}, target=out["id"])
    return out
