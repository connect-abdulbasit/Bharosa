from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import Case, User
from app.services.serialize import iso, latest_decision
from contracts.enums import Role
from contracts.schemas import QueueResponse

router = APIRouter(tags=["queue"])
AI_ACTIONS = {"auto_handle", "ask_more", "send_to_human"}


@router.get("/queue", response_model=QueueResponse)
def review_queue(user=Depends(require_role(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    """with_officer + needs_more_proof, sorted by risk (high first), confidence (low first), then age (oldest first)."""
    cases = db.execute(select(Case).where(Case.status.in_(["with_officer", "needs_more_proof"]))
                       .order_by(Case.risk_score.desc(), Case.confidence.asc(), Case.updated_at.asc())).scalars().all()
    items = []
    for c in cases:
        dec = latest_decision(db, c.id)
        action = dec.action if dec and dec.action in AI_ACTIONS else "send_to_human"
        citizen = db.get(User, c.citizen_id)
        items.append({"case_id": c.id, "citizen_name": citizen.name if citizen else "", "risk_score": c.risk_score,
                      "confidence": c.confidence, "recommended_action": action,
                      "reasons": list(dec.reasons) if dec else [],
                      "ai_reason": (dec.reasons[0] if dec and dec.reasons else None), "waiting_since": iso(c.updated_at)})
    return {"items": items}
