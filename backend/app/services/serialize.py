"""DB rows -> contract response dicts."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Claim, Consent, ConsentEvent, Decision, User
from app.models import Case
from app.services.consent import PURPOSE


def iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mask_cnic(cnic: Optional[str]) -> str:
    return "%s-*******-%s" % (cnic[:5], cnic[-1]) if cnic and len(cnic) == 13 else "*************"


def latest_claim(db: Session, case_id: str) -> Optional[Claim]:
    return db.execute(select(Claim).where(Claim.case_id == case_id).order_by(Claim.id.desc())).scalars().first()


def latest_decision(db: Session, case_id: str) -> Optional[Decision]:
    return db.execute(select(Decision).where(Decision.case_id == case_id).order_by(Decision.created_at.desc())).scalars().first()


def case_snapshot(case: Case) -> Dict[str, Any]:
    """Small JSON-safe view used for audit before/after."""
    return {"status": case.status, "assigned_to": case.assigned_to, "priority": case.priority,
            "current_step": case.current_step}


def case_summary(db: Session, case: Case) -> Dict[str, Any]:
    citizen = db.get(User, case.citizen_id)
    claim = latest_claim(db, case.id)
    amount = 0
    claim_type = "missing"
    if claim is not None:
        claim_type = claim.claim_type
        amount = max(claim.expected_amount - claim.received_amount, 0)
    return {"id": case.id, "citizen_name": citizen.name if citizen else "", "status": case.status,
            "claim_type": claim_type, "amount_claimed_pkr": amount, "risk_score": case.risk_score,
            "confidence": case.confidence, "assigned_to": case.assigned_to,
            "created_at": iso(case.created_at), "updated_at": iso(case.updated_at)}


def case_detail(db: Session, case: Case) -> Dict[str, Any]:
    out = case_summary(db, case)
    citizen = db.get(User, case.citizen_id)
    dec = latest_decision(db, case.id)
    out.update({
        "cnic_masked": mask_cnic(citizen.cnic if citizen else None),
        "programme": "Sahara Relief Programme",
        "notes": list(case.notes or []),
        "decision": None, "explanation_ur": None, "explanation_en": None,
        "pipeline_steps": [], "rule_version": None,
    })
    if dec is not None:
        out["decision"] = {"action": dec.action, "confidence": dec.confidence, "reasons": dec.reasons,
                           "trace": dec.trace, "rule_version": dec.rule_version,
                           "requires_officer_approval": True, "model_version": dec.model_version,
                           "decided_by": dec.decided_by}
        out["rule_version"] = dec.rule_version
        out["explanation_ur"] = (dec.trace or {}).get("explanation_ur")
        out["explanation_en"] = (dec.trace or {}).get("explanation_en")
    claim = latest_claim(db, case.id)
    state = (claim.data or {}).get("pipeline") if claim else None
    if state:
        from app.services.pipeline import steps_view  # lazy: pipeline imports this module

        out["pipeline_steps"] = steps_view(state)
    elif case.current_step:
        out["pipeline_steps"] = [{"step": case.current_step, "status": "current", "detail": ""}]
    return out


def consent_record(db: Session, c: Consent) -> Dict[str, Any]:
    events = db.execute(select(ConsentEvent).where(ConsentEvent.consent_id == c.id).order_by(ConsentEvent.created_at)).scalars().all()
    granted_at = next((iso(e.created_at) for e in reversed(events) if e.action == "grant"), None)
    withdrawn_at = next((iso(e.created_at) for e in reversed(events) if e.action == "withdraw"), None)
    if c.status == "granted":
        withdrawn_at = None
    return {"id": c.id, "citizen_id": c.citizen_id, "scope": c.scope, "granted": c.status == "granted",
            "granted_at": granted_at, "withdrawn_at": withdrawn_at,
            "shared_with": [c.granted_to] if c.granted_to else [], "purpose": PURPOSE.get(c.scope, "")}
