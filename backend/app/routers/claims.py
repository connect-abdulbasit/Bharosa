"""Claims: POST /claims saves the input and starts the pipeline in the BACKGROUND (202); poll GET /claims/{id}/progress."""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import ANY_ROLE, require_role
from app.db import get_db
from app.models import Claim, Document, User
from app.routers.cases import get_visible_case
from app.routing import CompactRoute
from app.services import audit, jobs, pipeline
from app.services.access import resolve_citizen
from contracts.enums import Role
from contracts.schemas import ClaimAccepted, ClaimCreate, ClaimProgress, ClaimResponse

router = APIRouter(tags=["claims"], route_class=CompactRoute)

CLAIM_EXAMPLES = {
    "citizen": {"summary": "A citizen speaks (transcript from the voice step)",
                "value": {"transcript": "mujhe is mahine ke paisay nahi mile", "document_id": None}},
    "helper": {"summary": "A helper files for a linked citizen",
               "value": {"transcript": "mujhe paisay kam mile hain", "on_behalf_of": "u-citizen-2"}},
}


def _claim_and_case(db: Session, user: User, claim_id: str):
    claim = db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim, get_visible_case(db, user, claim.case_id)  # 404 when the user may not see it


def _accepted(db: Session, case, claim) -> dict:
    db.refresh(case)
    db.refresh(claim)
    out = pipeline.response(db, case, claim)
    out.update(current_step=case.current_step or "queued", finished=bool((claim.data or {}).get("pipeline", {}).get("finished")),
               progress_url="/claims/%s/progress" % claim.id)
    return out


@router.post("/claims", response_model=ClaimAccepted, status_code=202, summary="File a claim (starts the agent in the background)")
def create_claim(body: ClaimCreate = Body(..., openapi_examples=CLAIM_EXAMPLES),
                 user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Saves the claim and returns **202** immediately with `case_id` and `current_step`. The agent (extract, ID photo,
    identity + ledger lookups, name match, decide, explain, notify) runs in the background: poll
    `GET /claims/{id}/progress` (ETag supported). Helpers must name the citizen (`on_behalf_of`) and pass the family link check."""
    citizen = db.get(User, resolve_citizen(db, user, body.on_behalf_of))
    if body.cnic and citizen.cnic and body.cnic != citizen.cnic:
        raise HTTPException(status_code=422, detail="This ID number does not belong to the account the claim is for")
    if body.document_id:
        doc = db.get(Document, body.document_id)
        if doc is None or doc.owner_id != citizen.id or doc.case_id is not None:
            raise HTTPException(status_code=422, detail="Unknown or already used document")
    case, claim = pipeline.create(db, user, citizen, body.transcript, body.document_id)
    job = jobs.enqueue(db, "claim_start", claim, user.id)
    db.commit()
    jobs.submit(job.id)
    return _accepted(db, case, claim)


@router.get("/claims/{claim_id}", response_model=ClaimResponse, summary="Full claim result")
def get_claim(claim_id: str, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    claim, case = _claim_and_case(db, user, claim_id)
    return pipeline.response(db, case, claim)


@router.get("/claims/{claim_id}/progress", response_model=ClaimProgress, summary="Cheap progress poll (ETag)")
def claim_progress(claim_id: str, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    """Tiny payload: `current_step`, `status`, steps finished. Send `If-None-Match` with the last ETag: unchanged => `304`, no body."""
    claim, case = _claim_and_case(db, user, claim_id)
    return pipeline.progress(case, claim, jobs.latest_status(db, claim.id))


@router.post("/claims/{claim_id}/resume", response_model=ClaimAccepted, status_code=202, summary="Continue a paused claim")
def resume_claim(claim_id: str, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Continue from the saved step (e.g. after a mock came back, or consent was granted again). Idempotent:
    a finished claim, or one that is already queued/running, is returned unchanged."""
    claim, case = _claim_and_case(db, user, claim_id)
    if pipeline.can_resume(case, claim):
        busy = jobs.latest_status(db, claim.id) in jobs.ACTIVE
        if not busy:
            audit.log(db, "user", user.id, "claim.resume", "claim", claim.id,
                      after={"from_step": case.current_step, "failed": (claim.data or {}).get("pipeline", {}).get("failed")})
        job = jobs.enqueue(db, "claim_resume", claim, user.id)
        db.commit()
        jobs.submit(job.id)
    return _accepted(db, case, claim)
