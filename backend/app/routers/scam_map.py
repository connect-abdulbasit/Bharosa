from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.routing import CompactRoute
from app.services import scam_map
from contracts.enums import Role
from contracts.schemas import ScamMapResponse

router = APIRouter(tags=["scam-map"], route_class=CompactRoute)


@router.get("/scam-map", response_model=ScamMapResponse, summary="Scam checks by area, day and reason (counts only)")
def get_scam_map(days: int = Query(30, ge=1, le=90, description="Look-back window in days"),
                 user=Depends(require_role(Role.officer, Role.admin, Role.auditor)), db: Session = Depends(get_db)):
    """Aggregated scam verdicts from `checked_messages`. **Counts only**: no message text, senders or user ids. Areas and reasons with
    fewer than 3 reports are grouped as `other` so a tiny village or a rare message cannot be singled out."""
    return scam_map.build(db, days)
