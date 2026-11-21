"""Consent: list my consents, grant, withdraw (with reason), correct data. Every change is audited."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
from app.auth import require_role
from app.db import get_db
from app.models import Consent, User
from app.services import audit
from app.services import consent as consent_service
from app.services.access import linked_citizen_ids, resolve_citizen
from app.services.serialize import consent_record
from contracts.enums import Role
from contracts.schemas import (ConsentCorrection, ConsentGrant, ConsentListResponse, ConsentRecord, ConsentWithdraw)

router = APIRouter(tags=["consent"], route_class=CompactRoute)
OWNERS = (Role.citizen, Role.helper)
CORRECTABLE = {"name": "name", "phone": "phone"}


def _own_consent(db: Session, user: User, consent_id: str) -> Consent:
    c = db.get(Consent, consent_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Consent not found")
    allowed = (c.citizen_id == user.id) if user.role == Role.citizen.value else (c.citizen_id in linked_citizen_ids(db, user.id))
    if not allowed:
        raise HTTPException(status_code=404, detail="Consent not found")
    return c


@router.get("/consent", response_model=ConsentListResponse)
def list_consent(citizen_id: Optional[str] = None, user: User = Depends(require_role(*OWNERS)), db: Session = Depends(get_db)):
    if user.role == Role.helper.value and not citizen_id:
        ids = linked_citizen_ids(db, user.id)  # all linked citizens
    else:
        ids = {resolve_citizen(db, user, citizen_id)}
    rows = db.execute(select(Consent).where(Consent.citizen_id.in_(ids)).order_by(Consent.citizen_id, Consent.scope)).scalars().all()
    return {"items": [consent_record(db, c) for c in rows]}


@router.post("/consent", response_model=ConsentRecord)
def grant_consent(body: ConsentGrant, user: User = Depends(require_role(*OWNERS)), db: Session = Depends(get_db)):
    cid = resolve_citizen(db, user, body.citizen_id)
    confirmed_by = None
    if user.role == Role.helper.value:  # granting on someone's behalf needs the citizen's own PIN
        consent_service.verify_citizen_pin(db, user, cid, body.pin)
        confirmed_by = cid
    scope = body.scope.value
    c = consent_service.get_consent(db, cid, scope)
    before = {"status": c.status} if c else None
    recipient = body.shared_with[0] if body.shared_with else consent_service.DEFAULT_RECIPIENT[scope]
    if c is None:
        c = Consent(citizen_id=cid, scope=scope, granted_to=recipient, status="granted")
        db.add(c)
        db.flush()
    else:
        c.status, c.granted_to = "granted", recipient
    consent_service.record_event(db, c, "grant", user.id, confirmed_by=confirmed_by)
    audit.log(db, "user", user.id, "consent.grant", "consent", c.id, before=before, after={"status": "granted", "scope": scope, "citizen_id": cid, "confirmed_by": confirmed_by})
    db.commit()
    return consent_record(db, c)


@router.post("/consent/{consent_id}/withdraw", response_model=ConsentRecord)
def withdraw_consent(consent_id: str, body: Optional[ConsentWithdraw] = None, user: User = Depends(require_role(*OWNERS)),
                     db: Session = Depends(get_db)):
    c = _own_consent(db, user, consent_id)
    if c.status == "withdrawn":
        raise HTTPException(status_code=409, detail="Consent already withdrawn")
    reason = body.reason if body else None
    before = {"status": c.status}
    c.status = "withdrawn"
    consent_service.record_event(db, c, "withdraw", user.id, reason)
    audit.log(db, "user", user.id, "consent.withdraw", "consent", c.id, before=before,
              after={"status": "withdrawn", "scope": c.scope, "citizen_id": c.citizen_id, "reason": reason})
    db.commit()
    return consent_record(db, c)


@router.post("/consent/{consent_id}/correct", response_model=ConsentRecord)
def correct_data(consent_id: str, body: ConsentCorrection, user: User = Depends(require_role(*OWNERS)), db: Session = Depends(get_db)):
    """Correct a wrong data item the consent covers (name or phone). Logged with before/after."""
    c = _own_consent(db, user, consent_id)
    if body.field not in CORRECTABLE:
        raise HTTPException(status_code=422, detail="field must be one of %s" % sorted(CORRECTABLE))
    if not body.new_value.strip():
        raise HTTPException(status_code=422, detail="new_value must not be empty")
    citizen = db.get(User, c.citizen_id)
    attr = CORRECTABLE[body.field]
    old = getattr(citizen, attr)
    setattr(citizen, attr, body.new_value.strip())
    consent_service.record_event(db, c, "correct", user.id, "corrected %s" % body.field)
    audit.log(db, "user", user.id, "consent.correct", "user", citizen.id, before={body.field: old}, after={body.field: getattr(citizen, attr)})
    db.commit()
    return consent_record(db, c)
