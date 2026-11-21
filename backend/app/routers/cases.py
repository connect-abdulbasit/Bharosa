"""Cases on the database. Row-level rules:
- citizen: own cases only; helper: cases of linked citizens only; officer/admin/auditor: all.
- Objects the user may not see answer 404 (existence is not leaked).
- Every status change is audited via services.cases.change_status.
"""
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
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

router = APIRouter(tags=["cases"], route_class=CompactRoute)

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


@router.post("/cases/{case_id}/decide", response_model=CaseDetail, summary="Officer decision (reason required)")
def decide(case_id: str, body: OfficerDecision = Body(..., openapi_examples={
        "approve": {"summary": "Approve (releases a needed payment once)", "value": {"action": "approve", "reason": "Ledger shows 8000 of 12000"}},
        "ask_more": {"summary": "Ask for more proof", "value": {"action": "ask_more", "reason": "ID photo is blurry"}}}),
           user: User = Depends(require_role(Role.officer)), db: Session = Depends(get_db)):
    """Officer decision (approve / reject / ask_more) with a REQUIRED reason, stored with `decided_by` = officer id.
    Approving a case that needs a payment pays through the (mock) payments rail **exactly once**: the idempotency key
    `case_id:decision_id` is saved on the decision BEFORE the call, so a retry (or a second approval) reuses it."""
    if body.action not in OFFICER_ACTIONS:
        raise HTTPException(status_code=422, detail="action must be one of approve, reject, ask_more")
    reason = (body.reason or body.note or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="A reason is required for every officer decision")
    action = "ask_more" if body.action == "request_more" else body.action
    new_status = OFFICER_ACTIONS[action]
    get_visible_case(db, user, case_id)
    case = db.execute(select(Case).where(Case.id == case_id).with_for_update()).scalar_one()  # serialises concurrent approvals (Postgres)
    if not case_service.can_move(case, new_status):
        raise HTTPException(status_code=409, detail="Cannot move a case from '%s' to '%s'" % (case.status, new_status))
    rule = rule_service.get_active_rule(db)

    claim = latest_claim(db, case.id)
    shortfall = (claim.expected_amount - claim.received_amount) if claim else 0
    dec = None
    payment = None
    if action == "approve" and shortfall > 0:
        citizen = db.get(User, case.citizen_id)
        consent_service.require(db, citizen.id, ConsentScope.payments, user, "release approved payment")  # 403 if withdrawn
        # Reuse an earlier attempt for this case (it already owns an idempotency key) instead of starting a new payment.
        dec = db.execute(select(Decision).where(Decision.case_id == case.id, Decision.action == "approve",
                                                Decision.idempotency_key.isnot(None)).order_by(Decision.created_at.desc())).scalars().first()
        if dec is None:
            dec = Decision(case_id=case.id, action="approve", confidence=1.0, reasons=[reason], trace={"officer_decision": True},
                           rule_id=rule.rule_id, rule_version=rule.version, decided_by=user.id, payment_status="pending")
            db.add(dec)
            db.flush()
            dec.idempotency_key = "%s:%s" % (case.id, dec.id)
            audit.log(db, "user", user.id, "payment.initiated", "case", case.id, after={"amount_pkr": shortfall, "idempotency_key": dec.idempotency_key})
            db.commit()  # the key is durable BEFORE any money moves
        dec.decided_by, dec.reasons = user.id, [reason]
        via = "earlier attempt"  # payment already made by a previous attempt that did not finish the approval
        if dec.payment_status != "paid":
            try:
                res = get_mocks_client().disburse(case.id, citizen.cnic or "", shortfall, dec.idempotency_key)
            except MockUnavailable as exc:
                dec.payment_status = "failed"
                audit.log(db, "agent", "agent:payments", "payment.failed", "case", case.id,
                          after={"amount_pkr": shortfall, "idempotency_key": dec.idempotency_key, "error": str(exc)[:200]})
                db.commit()
                raise HTTPException(status_code=503, detail="The payment could not be released (%s). Nothing was changed; please try again." % exc)
            via = res.get("via")
            dec.payment_ref, dec.payment_status = res.get("payment_ref"), "paid"
            audit.log(db, "user", user.id, "payment.release", "case", case.id,
                      after={"amount_pkr": shortfall, "payment_ref": dec.payment_ref, "via": via, "idempotency_key": dec.idempotency_key})
            db.commit()  # the payment record is durable BEFORE the status changes
        payment = {"payment_ref": dec.payment_ref, "amount_pkr": shortfall, "via": via,
                   "idempotency_key": dec.idempotency_key, "simulated": True}

    case_service.change_status(db, case, new_status, user, "case.decide", note="Officer decision %s: %s" % (action, reason))
    if dec is None:
        dec = Decision(case_id=case.id, action=action, confidence=1.0, reasons=[reason], trace={}, rule_id=rule.rule_id,
                       rule_version=rule.version, decided_by=user.id)
        db.add(dec)
    dec.trace = {"officer_decision": True, "payment": payment}
    db.flush()
    audit.log(db, "user", user.id, "decision.create", "decision", dec.id,
              after={"case_id": case.id, "action": action, "reason": reason, "rule_id": rule.rule_id, "rule_version": rule.version,
                     "payment_ref": dec.payment_ref})
    if payment:
        case_service.add_note(case, user.id, "Payment released: PKR %d (reference %s)" % (shortfall, payment["payment_ref"]))
    db.commit()
    return case_detail(db, case)


@router.post("/cases/{case_id}/close", response_model=CaseDetail)
def close(case_id: str, body: CloseRequest, user: User = Depends(require_role(Role.officer, Role.admin)), db: Session = Depends(get_db)):
    case = get_visible_case(db, user, case_id)
    case_service.change_status(db, case, "closed", user, "case.close", note="Closed: %s" % body.resolution)
    db.commit()
    return case_detail(db, case)

