"""Versioned decision rules (json-logic). TODO(Basit): persist, never edit in place, store version on each decision."""
from contracts.schemas import RuleVersion

DEFAULT_RULE = RuleVersion(rule_id="rule-sahara-1", version=3)


def get_active_rule() -> RuleVersion:
    return DEFAULT_RULE
