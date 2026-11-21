"""Digital Twin support: re-run ONLY the decide step of past AI decisions under a proposed rule. Read-only."""
from collections import Counter
from typing import Any, Dict, List, Optional

import bharosa_ai as ai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Claim, Decision
from contracts.ai_interface import ClaimDraft, DocumentReading, Evidence, MatchResult
from contracts.schemas import Payment, RuleVersion

MAX_EXAMPLES = 20


def _inputs(claim: Optional[Claim]) -> Optional[Dict[str, Any]]:
    """Everything decide() needs, from what the pipeline stored. None for decisions that have no stored inputs (seeded samples)."""
    state = ((claim.data or {}).get("pipeline") if claim else None) or {}
    out = state.get("outputs", {})
    if "extract_claim" not in out or "match_person" not in out or "ledger_lookup" not in out:
        return None
    return {"draft": out["extract_claim"]["draft"], "match": out["match_person"]["match"], "payments": out["ledger_lookup"].get("payments", []),
            "doc": out.get("read_document", {}), "flags_found": state.get("flags_found", []), "payment_needed": bool(state.get("payment_needed"))}


def simulate(db: Session, rule: RuleVersion) -> Dict[str, Any]:
    latest: Dict[str, Decision] = {}
    for d in db.execute(select(Decision).where(Decision.decided_by == "ai").order_by(Decision.created_at)).scalars():
        latest[d.case_id] = d  # the latest AI decision per case
    transitions: Counter = Counter()
    examples: List[Dict[str, str]] = []
    simulated = skipped = changed = 0
    for case_id, old in latest.items():
        claim = db.execute(select(Claim).where(Claim.case_id == case_id).order_by(Claim.id.desc())).scalars().first()
        inp = _inputs(claim)
        if inp is None:
            skipped += 1
            continue
        doc = inp["doc"]
        evidence = Evidence(match=MatchResult(**inp["match"]),
                            document=DocumentReading(**doc["reading"]) if doc.get("usable") else None,
                            ledger=[Payment(**{k: v for k, v in p.items() if k in Payment.model_fields}) for p in inp["payments"]],
                            red_flags=[f for f in inp["flags_found"] if f in rule.red_flags], payment_step=inp["payment_needed"])
        new = ai.decide(ClaimDraft(**inp["draft"]), evidence, rule).action.value
        simulated += 1
        if new != old.action:
            changed += 1
            transitions["%s -> %s" % (old.action, new)] += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({"case_id": case_id, "old_action": old.action, "new_action": new})
    return {"total_cases": len(latest), "simulated_cases": simulated, "skipped_no_inputs": skipped, "would_change": changed,
            "by_transition": dict(transitions), "examples": examples}
