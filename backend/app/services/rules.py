"""Versioned decision rules (json-logic). Versions are immutable; every decision stores the version used."""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Rule, RuleVersion
from app.services.jsonlogic import RuleError, validate_logic
from app.services.serialize import iso
from contracts import schemas

RULE_ID = "rule-stipend-short-payment"

DEFAULT_LOGIC: Dict[str, Any] = {
    "if": [{"and": [{">=": [{"var": "confidence"}, 0.9]}, {"==": [{"var": "red_flags.length"}, 0]}]}, "auto_handle",
           {"if": [{">=": [{"var": "confidence"}, 0.6]}, "ask_more", "send_to_human"]}]
}
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "auto_handle_min": 0.90, "ask_more_min": 0.60,
    "red_flags": ["short_payment", "duplicate_payment", "lookalike_sender", "mock_service_failure", "claim_contradicts_ledger"],
}


def validate_rule(logic: Dict[str, Any], auto_handle_min: float, ask_more_min: float, red_flags: Any) -> None:
    """Raise jsonlogic.RuleError (-> HTTP 422) with a clear message if the rule is not safe to publish."""
    if not (0.0 <= ask_more_min <= auto_handle_min <= 1.0):
        raise RuleError("Need 0 <= ask_more_min <= auto_handle_min <= 1 (got ask_more_min=%s, auto_handle_min=%s)" % (ask_more_min, auto_handle_min))
    if auto_handle_min < 0.5:
        raise RuleError("auto_handle_min below 0.5 is not allowed: it would auto-handle uncertain cases")
    if not isinstance(red_flags, list) or len(red_flags) > 30 or any(not isinstance(f, str) or not f or len(f) > 50 for f in red_flags):
        raise RuleError("red_flags must be a list of up to 30 short names")
    if logic:
        validate_logic(logic)


def get_version(db: Session, rule_id: str, version: int) -> Optional[RuleVersion]:
    return db.execute(select(RuleVersion).where(RuleVersion.rule_id == rule_id, RuleVersion.version == version)).scalar_one_or_none()


def to_contract(rule: Rule, rv: RuleVersion) -> schemas.RuleVersion:
    t = rv.thresholds or {}
    return schemas.RuleVersion(rule_id=rule.id, version=rv.version, name=rule.name,
                               auto_handle_min=t.get("auto_handle_min", 0.9), ask_more_min=t.get("ask_more_min", 0.6),
                               red_flags=t.get("red_flags", []), logic=rv.logic or {}, created_by=rv.created_by,
                               created_at=iso(rv.created_at), note=rv.note)


def get_active_rule(db: Session, rule_id: str = RULE_ID) -> schemas.RuleVersion:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise LookupError("rule %s not found (run make seed)" % rule_id)
    rv = get_version(db, rule.id, rule.active_version)
    assert rv is not None
    return to_contract(rule, rv)
