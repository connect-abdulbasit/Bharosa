"""Cases on the database. Row-level rules:
- citizen: own cases only; helper: cases of linked citizens only; officer/admin/auditor: all.
- Objects the user may not see answer 404 (existence is not leaked).
- Every status change is audited via services.cases.change_status.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import ANY_ROLE, require_role
from app.db import get_db
from app.models import Case, Claim, Decision, User
from app.services import audit
from app.services import cases as case_service
from app.services import consent as consent_service
from app.services import rules as rule_service
from app.services.access import resolve_citizen, visible_citizen_ids
from app.services.mock_errors import MockUnavailable
from app.services.mocks_client import get_mocks_client
from app.services.serialize import case_detail, case_snapshot, case_summary, latest_claim
from contracts.enums import ConsentScope, Role
from contracts.schemas import (AssignRequest, CaseCreate, CaseDetail, CaseListResponse, CloseRequest, EscalateRequest,
                               OfficerDecision)

router = APIRouter(tags=["cases"])

OFFICER_ACTIONS = {"approve": "approved", "reject": "rejected", "ask_more": "needs_more_proof", "request_more": "needs_more_proof"}


def get_visible_case(db: Session, user: User, case_id: str) -> Case:
    case = db.get(Case, case_id)
    ids = visible_citizen_ids(db, user)
    if case is None or (ids is not None and case.citizen_id not in ids):
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.get("/cases", response_model=CaseListResponse)
def list_cases(status: Optional[str] = None, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    stmt = select(Case).order_by(Case.updated_at.desc())
    ids = visible_citizen_ids(db, user)
    if ids is not None:
        stmt = stmt.where(Case.citizen_id.in_(ids))
    if status:
        stmt = stmt.where(Case.status == status)
    rows: List[Case] = list(db.execute(stmt).scalars())
    return {"items": [case_summary(db, c) for c in rows], "total": len(rows)}


@router.post("/cases", response_model=CaseDetail)
def create_case(body: CaseCreate, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    citizen_id = resolve_citizen(db, user, body.citizen_id)
    case = Case(citizen_id=citizen_id, created_by=user.id, status="submitted", current_step="submitted", notes=[])
    db.add(case)
    db.flush()
    db.add(Claim(case_id=case.id, claim_type=body.claim_type, expected_amount=body.amount_claimed_pkr, received_amount=0,
                 data={"source": "manual"}))
    if body.notes:
        case_service.add_note(case, user.id, body.notes)
    db.flush()
    audit.log(db, "user", user.id, "case.create", "case", case.id, before=None, after=case_snapshot(case))
    db.commit()
    return case_detail(db, case)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    return case_detail(db, get_visible_case(db, user, case_id))


@router.post("/cases/{case_id}/assign", response_model=CaseDetail)
def assign(case_id: str, body: AssignRequest, user: User = Depends(require_role(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    case = get_visible_case(db, user, case_id)
    target = db.get(User, body.officer_id)
    if target is None or target.role not in (Role.officer.value, Role.admin.value):
        raise HTTPException(status_code=422, detail="officer_id must be an officer or admin")
    if case.status == "closed":
        raise HTTPException(status_code=409, detail="Case is closed")
    before = case_snapshot(case)
    case.assigned_to = target.id
    case_service.add_note(case, user.id, "Assigned to %s" % target.name)
    db.flush()
    audit.log(db, "user", user.id, "case.assign", "case", case.id, before=before, after=case_snapshot(case))
    db.commit()
    return case_detail(db, case)


@router.post("/cases/{case_id}/escalate", response_model=CaseDetail)
def escalate(case_id: str, body: EscalateRequest, user: User = Depends(require_role(Role.helper, Role.officer)), db: Session = Depends(get_db)):
    case = get_visible_case(db, user, case_id)
    case.priority = "high"
    case_service.change_status(db, case, "with_officer", user, "case.escalate", note="Escalated: %s" % body.reason, step="with_officer")
    db.commit()
    return case_detail(db, case)


@router.post("/cases/{case_id}/decide", response_model=CaseDetail)
def decide(case_id: str, body: OfficerDecision, user: User = Depends(require_role(Role.officer)), db: Session = Depends(get_db)):
    """Officer decision (approve / reject / ask_more) with a REQUIRED reason, stored with decided_by = officer id.
    Approving a case that needs a payment releases it through the (mock) payments channel and records it."""
    if body.action not in OFFICER_ACTIONS:
        raise HTTPException(status_code=422, detail="action must be one of approve, reject, ask_more")
    reason = (body.reason or body.note or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="A reason is required for every officer decision")
    action = "ask_more" if body.action == "request_more" else body.action
    new_status = OFFICER_ACTIONS[action]
    case = get_visible_case(db, user, case_id)
    if not case_service.can_move(case, new_status):
        raise HTTPException(status_code=409, detail="Cannot move a case from '%s' to '%s'" % (case.status, new_status))
    rule = rule_service.get_active_rule(db)

    payment = None
    claim = latest_claim(db, case.id)
    shortfall = (claim.expected_amount - claim.received_amount) if claim else 0
    if action == "approve" and shortfall > 0:
        citizen = db.get(User, case.citizen_id)
        consent_service.require(db, citizen.id, ConsentScope.complaints, user, "release approved payment")  # 403 if withdrawn
        try:
            res = get_mocks_client().complaint(citizen.cnic or "", "payment_topup",
                                               "Approved top-up of PKR %d for case %s by %s" % (shortfall, case.id, user.id))
        except MockUnavailable as exc:
            audit.log(db, "agent", "agent:payments", "payment.failed", "case", case.id, after={"amount_pkr": shortfall, "error": str(exc)[:200]})
            db.commit()
            raise HTTPException(status_code=503, detail="The payment could not be released (%s). Nothing was changed; please try again." % exc)
        payment = {"ticket_id": res.get("ticket_id"), "amount_pkr": shortfall, "channel": "mocks /complaints", "simulated": True}

    case_service.change_status(db, case, new_status, user, "case.decide", note="Officer decision %s: %s" % (action, reason))
    dec = Decision(case_id=case.id, action=action, confidence=1.0, reasons=[reason], trace={"officer_decision": True, "payment": payment},
                   rule_id=rule.rule_id, rule_version=rule.version, model_version=None, decided_by=user.id)
    db.add(dec)
    db.flush()
    audit.log(db, "user", user.id, "decision.create", "decision", dec.id,
              after={"case_id": case.id, "action": action, "reason": reason, "rule_id": rule.rule_id, "rule_version": rule.version})
    if payment:
        case_service.add_note(case, user.id, "Payment released: PKR %d (ticket %s)" % (shortfall, payment["ticket_id"]))
        audit.log(db, "user", user.id, "payment.release", "case", case.id, after=payment)
    db.commit()
    return case_detail(db, case)


@router.post("/cases/{case_id}/close", response_model=CaseDetail)
def close(case_id: str, body: CloseRequest, user: User = Depends(require_role(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    case = get_visible_case(db, user, case_id)
    case_service.change_status(db, case, "closed", user, "case.close", note="Closed: %s" % body.resolution)
    db.commit()
    return case_detail(db, case)

