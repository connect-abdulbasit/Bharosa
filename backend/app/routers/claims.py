from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.fixtures import fixture
from app.models import User
from app.services import audit
from app.services import consent as consent_service
from app.services.access import resolve_citizen
from contracts.enums import ConsentScope, Role
from contracts.schemas import ClaimCreate, ClaimResponse

router = APIRouter(tags=["claims"])


@router.post("/claims", response_model=ClaimResponse)
def create_claim(body: ClaimCreate, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    citizen_id = resolve_citizen(db, user, body.on_behalf_of)
    # Consent BEFORE any identity/payment lookup (raises ConsentRequired -> 403, logged).
    consent_service.require(db, citizen_id, ConsentScope.identity, user, "claim: identity lookup")
    consent_service.require(db, citizen_id, ConsentScope.payments, user, "claim: payment ledger lookup")
    # TODO(Basit): run services.pipeline (extract -> match -> ledger via mocks client -> decide) and persist.
    out = fixture("claim_create")
    audit.log(db, "user", user.id, "claim.create", "claim", out["claim_id"], after={"citizen_id": citizen_id, "stub": True})
    db.commit()
    return out
