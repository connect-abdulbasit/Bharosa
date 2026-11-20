"""Versioned decision rules (json-logic). Versions are immutable; every decision stores the version used."""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Rule, RuleVersion
from app.services.serialize import iso
from contracts import schemas

RULE_ID = "rule-stipend-short-payment"

DEFAULT_LOGIC: Dict[str, Any] = {
    "if": [{"and": [{">=": [{"var": "confidence"}, 0.9]}, {"==": [{"var": "red_flags.length"}, 0]}]}, "auto_handle",
           {"if": [{">=": [{"var": "confidence"}, 0.6]}, "ask_more", "send_to_human"]}]
}
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "auto_handle_min": 0.90, "ask_more_min": 0.60,
    "red_flags": ["short_payment", "duplicate_payment", "lookalike_sender", "mock_service_failure"],
}


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
