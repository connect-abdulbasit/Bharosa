from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
from app.auth import require_role
from app.db import get_db
from app.models import Rule, RuleVersion, User
from app.services import audit
from app.services import rules as rule_service
from app.services import simulate as simulation
from app.services.jsonlogic import RuleError
from app.services.serialize import iso
from contracts.enums import Role
from contracts.schemas import RuleListResponse, RuleSimulation, RuleVersionCreate, RuleVersionsResponse
from contracts.schemas import RuleVersion as RuleVersionOut

router = APIRouter(tags=["rules"], route_class=CompactRoute)
READERS = (Role.officer, Role.admin, Role.auditor)


def _inherit_flags(body: RuleVersionCreate, base) -> list:
    """Omitting `red_flags` keeps the current rule's flags (a missing field must never silently drop safeguards);
    only an explicit list (even an empty one) replaces them."""
    if "red_flags" in body.model_fields_set:
        return body.red_flags
    return list(((base.thresholds or {}).get("red_flags")) or []) if base is not None else []


def _rule(db: Session, rule_id: str) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("/rules", response_model=RuleListResponse)
def list_rules(user=Depends(require_role(*READERS)), db: Session = Depends(get_db)):
    items = []
    for r in db.execute(select(Rule)).scalars():
        rv = rule_service.get_version(db, r.id, r.active_version)
        items.append({"id": r.id, "name": r.name, "current_version": r.active_version, "updated_at": iso(rv.created_at) if rv else ""})
    return {"items": items}


@router.get("/rules/{rule_id}/versions", response_model=RuleVersionsResponse)
def list_versions(rule_id: str, user=Depends(require_role(*READERS)), db: Session = Depends(get_db)):
    rule = _rule(db, rule_id)
    rows = db.execute(select(RuleVersion).where(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version.desc())).scalars().all()
    return {"rule_id": rule.id, "versions": [rule_service.to_contract(rule, rv) for rv in rows]}


@router.post("/rules/{rule_id}/versions", response_model=RuleVersionOut)
def create_version(rule_id: str, body: RuleVersionCreate, user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    """Insert a NEW immutable version and make it active. No redeploy, old versions untouched."""
    rule = _rule(db, rule_id)
    prev = rule_service.get_version(db, rule.id, rule.active_version)
    red_flags = _inherit_flags(body, prev)
    try:
        rule_service.validate_rule(body.logic, body.auto_handle_min, body.ask_more_min, red_flags)
    except RuleError as exc:
        audit.log(db, "user", user.id, "rule.rejected", "rule", rule.id, after={"error": str(exc)[:300]})
        db.commit()
        raise HTTPException(status_code=422, detail="Invalid rule: %s" % exc)
    new_version = (db.execute(select(RuleVersion.version).where(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version.desc())).scalars().first() or 0) + 1
    rv = RuleVersion(rule_id=rule.id, version=new_version, logic=body.logic or (prev.logic if prev else {}),
                     thresholds={"auto_handle_min": body.auto_handle_min, "ask_more_min": body.ask_more_min, "red_flags": red_flags},
                     created_by=user.id, note=body.note)
    db.add(rv)
    before = {"active_version": rule.active_version}
    rule.active_version = new_version
    db.flush()
    audit.log(db, "user", user.id, "rule.new_version", "rule", rule.id, before=before,
              after={"active_version": new_version, "thresholds": rv.thresholds})
    db.commit()
    return rule_service.to_contract(rule, rv)


@router.post("/rules/{rule_id}/simulate", response_model=RuleSimulation, summary="What-if: re-run past decisions under a proposed rule (nothing saved)")
def simulate_rule(rule_id: str, body: RuleVersionCreate = Body(..., openapi_examples={
        "stricter": {"summary": "Raise auto_handle to 0.95", "value": {"auto_handle_min": 0.95, "ask_more_min": 0.6, "red_flags": ["short_payment"]}}}),
        user: User = Depends(require_role(Role.admin)), db: Session = Depends(get_db)):
    """Digital Twin support. Validates the proposal like a real publish, then re-runs **only the decide step** on the stored inputs
    (claim draft, name match, ledger, flags) of past AI decisions. Returns how many would change, a from -> to breakdown and up to 20
    example case ids. **Read-only**: the only write is one `rule.simulate` audit row. Seeded sample decisions have no stored inputs and are skipped."""
    rule = _rule(db, rule_id)
    base = rule_service.get_version(db, rule.id, rule.active_version)
    red_flags = _inherit_flags(body, base)  # omitted = keep the current flags (so a what-if never quietly drops safeguards)
    try:
        rule_service.validate_rule(body.logic, body.auto_handle_min, body.ask_more_min, red_flags)
    except RuleError as exc:
        raise HTTPException(status_code=422, detail="Invalid rule: %s" % exc)
    proposed = RuleVersionOut(rule_id=rule.id, version=rule.active_version + 1, name=rule.name, auto_handle_min=body.auto_handle_min,
                              ask_more_min=body.ask_more_min, red_flags=red_flags, logic=body.logic or (base.logic if base else {}))
    result = simulation.simulate(db, proposed)
    summary = {"auto_handle_min": body.auto_handle_min, "ask_more_min": body.ask_more_min, "red_flags": red_flags}
    audit.log(db, "user", user.id, "rule.simulate", "rule", rule.id, after=dict(summary, total_cases=result["total_cases"],
              would_change=result["would_change"], simulated_cases=result["simulated_cases"]))
    db.commit()
    return dict(result, rule_id=rule.id, current_version=rule.active_version, proposed=summary)
