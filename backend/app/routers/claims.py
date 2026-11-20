"""Claims: POST /claims runs the agent pipeline; POST /claims/{id}/resume continues it after a failure."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ANY_ROLE, require_role
from app.db import get_db
from app.models import Claim, Document, User
from app.routers.cases import get_visible_case
from app.services import pipeline
from app.services import rules as rule_service
from app.services.access import resolve_citizen
from app.services.mocks_client import get_mocks_client
from contracts.enums import Role
from contracts.schemas import ClaimCreate, ClaimResponse

router = APIRouter(tags=["claims"])


def _claim_and_case(db: Session, user: User, claim_id: str):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim, get_visible_case(db, user, claim.case_id)  # 404 when the user may not see it


@router.post("/claims", response_model=ClaimResponse)
def create_claim(body: ClaimCreate, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Helpers must name the citizen (on_behalf_of) and pass the family link check."""
    citizen = db.get(User, resolve_citizen(db, user, body.on_behalf_of))
    if body.cnic and citizen.cnic and body.cnic != citizen.cnic:
        raise HTTPException(status_code=422, detail="This ID number does not belong to the account the claim is for")
    if body.document_id:
        doc = db.get(Document, body.document_id)
        if doc is None or doc.owner_id != citizen.id or doc.case_id is not None:
            raise HTTPException(status_code=422, detail="Unknown or already used document")
    case, claim = pipeline.start(db, user, citizen, body.transcript, body.document_id, get_mocks_client(), rule_service.get_active_rule(db))
    return pipeline.response(db, case, claim)


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: str, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    claim, case = _claim_and_case(db, user, claim_id)
    return pipeline.response(db, case, claim)


@router.post("/claims/{claim_id}/resume", response_model=ClaimResponse)
def resume_claim(claim_id: str, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Continue from the saved step (e.g. after a mock came back, or consent was granted again). Idempotent."""
    claim, case = _claim_and_case(db, user, claim_id)
    citizen = db.get(User, case.citizen_id)
    pipeline.resume(db, user, citizen, case, claim, get_mocks_client(), rule_service.get_active_rule(db))
    db.refresh(case)
    db.refresh(claim)
    return pipeline.response(db, case, claim)
