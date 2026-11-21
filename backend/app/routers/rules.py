from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
from app.auth import require_role
from app.db import get_db
from app.models import Rule, RuleVersion, User
from app.services import audit
from app.services import rules as rule_service
from app.services.jsonlogic import RuleError
from app.services.serialize import iso
from contracts.enums import Role
from contracts.schemas import RuleListResponse, RuleVersionCreate, RuleVersionsResponse
from contracts.schemas import RuleVersion as RuleVersionOut

router = APIRouter(tags=["rules"], route_class=CompactRoute)
READERS = (Role.officer, Role.admin, Role.auditor)


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
    try:
        rule_service.validate_rule(body.logic, body.auto_handle_min, body.ask_more_min, body.red_flags)
    except RuleError as exc:
        audit.log(db, "user", user.id, "rule.rejected", "rule", rule.id, after={"error": str(exc)[:300]})
        db.commit()
        raise HTTPException(status_code=422, detail="Invalid rule: %s" % exc)
    prev = rule_service.get_version(db, rule.id, rule.active_version)
    new_version = (db.execute(select(RuleVersion.version).where(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version.desc())).scalars().first() or 0) + 1
    rv = RuleVersion(rule_id=rule.id, version=new_version, logic=body.logic or (prev.logic if prev else {}),
                     thresholds={"auto_handle_min": body.auto_handle_min, "ask_more_min": body.ask_more_min, "red_flags": body.red_flags},
                     created_by=user.id, note=body.note)
    db.add(rv)
    before = {"active_version": rule.active_version}
    rule.active_version = new_version
    db.flush()
    audit.log(db, "user", user.id, "rule.new_version", "rule", rule.id, before=before,
              after={"active_version": new_version, "thresholds": rv.thresholds})
    db.commit()
    return rule_service.to_contract(rule, rv)
