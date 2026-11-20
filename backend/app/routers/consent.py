from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import ConsentGrant, ConsentListResponse, ConsentRecord

router = APIRouter(tags=["consent"])
OWNERS = (Role.citizen, Role.helper)


@router.get("/consent", response_model=ConsentListResponse)
def list_consent(user=Depends(require_role(*OWNERS))):
    return fixture("consent_list")


@router.post("/consent", response_model=ConsentRecord)
def grant_consent(body: ConsentGrant, user=Depends(require_role(*OWNERS))):
    out = dict(fixture("consent_list")["items"][0], scope=body.scope.value, shared_with=body.shared_with)
    audit.log(user["user_id"], "consent.grant", {"granted": False}, {"scope": body.scope.value, "granted": True}, target=out["id"])
    return out


@router.post("/consent/{consent_id}/withdraw", response_model=ConsentRecord)
def withdraw_consent(consent_id: str, user=Depends(require_role(*OWNERS))):
    # TODO(Basit): persist; stop all future mock calls for that scope immediately.
    audit.log(user["user_id"], "consent.withdraw", {"granted": True}, {"granted": False}, target=consent_id)
    return fixture("consent_withdraw")
