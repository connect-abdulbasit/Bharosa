"""Read-only public API for partners (NGOs, helplines). Authenticate with `X-API-Key` (or a normal JWT).
Rate limited per key. Deliberately minimal data."""
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.apikey import Principal, public_access
from app.config import settings
from app.db import get_db
from app.limiter import key_or_ip, limiter
from app.models import Case
from app.routing import CompactRoute
from app.services import audit, scam
from app.services.access import visible_citizen_ids
from app.services.mocks_client import get_mocks_client
from app.services.serialize import iso
from contracts.schemas import MessageCheckRequest, MessageCheckResponse, PublicCaseStatus

router = APIRouter(prefix="/public", tags=["public"], route_class=CompactRoute)


@router.get("/cases/{case_id}/status", response_model=PublicCaseStatus, summary="Status of one case (minimal)")
@limiter.limit(lambda: settings.PUBLIC_RATE_LIMIT, key_func=key_or_ip)
def case_status(request: Request, case_id: str, principal: Principal = Depends(public_access("cases:read")), db: Session = Depends(get_db)):
    """Returns only `status`, `current_step` and `updated_at` (no names, amounts or notes). Needs scope `cases:read`.
    With a JWT the normal row rules apply (a citizen sees only their own case)."""
    case = db.get(Case, case_id)
    if principal.user is not None:
        ids = visible_citizen_ids(db, principal.user)
        if case is not None and ids is not None and case.citizen_id not in ids:
            case = None
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case.id, "status": case.status, "current_step": case.current_step, "updated_at": iso(case.updated_at)}


@router.post("/messages/check", response_model=MessageCheckResponse, summary="Is this message a scam?")
@limiter.limit(lambda: settings.PUBLIC_RATE_LIMIT, key_func=key_or_ip)
def check_message(request: Request, body: MessageCheckRequest = Body(..., openapi_examples={
        "scam": {"summary": "Fee request from a look-alike sender",
                 "value": {"text": "Pay Rs 500 fee at http://bit.ly/x to receive your relief money", "sender": "9O9O", "area": "Malir"}}}),
        principal: Principal = Depends(public_access("messages:check")), db: Session = Depends(get_db)):
    """Classifies the message and checks the sender against the official list. Needs scope `messages:check`.
    Stores only a hash of the text. Never claims a message is genuine when the sender is not official."""
    out = scam.check_message(db, get_mocks_client(), body.text, body.sender, body.area)
    audit.log(db, "ai", "ai:classify_message", "ai.classify_message", "message", scam.text_hash(body.text)[:16],
              after={"label": out["label"], "confidence": out["confidence"], "sender": body.sender[:60], "official_sender": out["official_sender"],
                     "model_version": out["model_version"], "requested_by": "%s:%s" % (principal.kind, principal.id)})
    db.commit()
    return out
