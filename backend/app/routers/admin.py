"""Demo controls (admin only, and only while DEMO_MODE=1): restore the known demo state, break the in-process fake mocks."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import demo
from app.auth import require_role
from app.config import settings
from app.db import get_db
from app.fake_mocks_client import CHAOS
from app.models import User
from app.routing import CompactRoute
from app.services import audit
from app.services.mocks_client import mocks_status
from contracts.enums import Role

router = APIRouter(prefix="/admin/demo", tags=["admin"], route_class=CompactRoute)


class ResetRequest(BaseModel):
    include_rules: bool = False  # also restore rule v1 and DROP the rule version history


class ChaosRequest(BaseModel):
    identity_down: Optional[bool] = None
    ledger_down: Optional[bool] = None
    payments_down: Optional[bool] = None


def _need_demo_mode() -> None:
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo controls are disabled (DEMO_MODE=0)")


@router.post("/reset", summary="Restore the known demo state (wipes cases, claims, decisions, jobs, checks, consent changes)")
def reset_demo(body: ResetRequest = Body(ResetRequest(), openapi_examples={"default": {"summary": "Keep rules", "value": {"include_rules": False}},
                                                                            "pristine": {"summary": "Also restore rule v1", "value": {"include_rules": True}}}),
               user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    """Wipes cases, claims, decisions, jobs, ID photos, checked messages and consent changes, restores the seeded users, then re-seeds
    the 5 sample cases, the 6 named demo scenarios and 60 scam checks. **Rules and their version history are kept** unless
    `include_rules` is true. The append-only audit log is never wiped; the reset itself is audited (`demo.reset`)."""
    _need_demo_mode()
    return demo.reset(db, user, include_rules=body.include_rules)


@router.get("/chaos", summary="Outage switches of the in-process fake mocks")
def get_chaos(user: User = Depends(require_role(Role.admin))):
    _need_demo_mode()
    return dict(CHAOS, mocks=mocks_status(), note="These switches only affect the in-process fake mocks. With real mocks use their Chaos Panel (POST /chaos).")


@router.post("/chaos", summary="Break or fix the fake identity / ledger / payments service (demo scenario 6)")
def set_chaos(body: ChaosRequest = Body(..., openapi_examples={"identity_down": {"summary": "Identity service down", "value": {"identity_down": True}}}),
              user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    _need_demo_mode()
    before = dict(CHAOS)
    for k, v in body.model_dump(exclude_none=True).items():
        CHAOS[k] = v
    audit.log(db, "user", user.id, "demo.chaos", "system", None, before=before, after=dict(CHAOS))
    db.commit()
    return dict(CHAOS, mocks=mocks_status())
