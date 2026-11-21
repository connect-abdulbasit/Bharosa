"""decide: combine the evidence, apply the ACTIVE rule version, return an action with reasons and a trace.

Pure and deterministic (the backend re-runs it on stored inputs for the Digital Twin simulation).

- Combined confidence is the weakest link: the minimum of the available component confidences.
- Hard stops always go to a person, whatever the confidence: any red flag, a failed service check, a name that did
  not match the identity record, a rule that is not valid, or (when OCR read the ID photo) a CNIC or a name on the card that
  disagrees with the CNIC or the name given (`document_mismatch`, `document_name_mismatch`).
- An unclear ID photo can never be auto-handled (capped at ask_more).
- Otherwise the thresholds come ONLY from the RuleVersion argument. `rule.logic` (json-logic) is NOT evaluated on
  purpose: the backend never evaluates it either and its default hard-codes 0.9 / 0.6, so honouring it would silently
  override an admin's new thresholds.
- `requires_officer_approval` is always True: any payment needs an officer (the backend hard-codes True as well).
"""
import re
from typing import Any, Dict, List

from bharosa_ai._shared import BLUR_RETAKE
from bharosa_ai.matching import MATCH_MIN, _align, _tokens
from contracts.ai_interface import ClaimDraft, Decision, Evidence
from contracts.enums import DecisionAction
from contracts.schemas import RuleVersion

MODEL_VERSION = "decide-rules-1.0"


def _unique(items: List[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def decide(claim: ClaimDraft, evidence: Evidence, rule: RuleVersion) -> Decision:
    names = ["claim"]
    parts = [claim.confidence]
    if evidence.match is not None:
        names.append("match")
        parts.append(evidence.match.confidence)
    if evidence.document is not None:
        names.append("document")
        parts.append(evidence.document.confidence)
    if evidence.verdict is not None:
        names.append("message")
        parts.append(evidence.verdict.confidence)
    confidence = min(parts)  # weakest link
    weakest = names[parts.index(confidence)]

    flags = _unique(list(evidence.red_flags) + (["mock_service_failure"] if evidence.mock_failures else []))
    hard_stops = list(flags)
    reasons: List[str] = []
    if flags:
        reasons.append("Red flags present: %s" % ", ".join(flags))
    if evidence.match is not None and evidence.match.match_id is None:
        hard_stops.append("name_not_matched")
        reasons.append("The name in the claim does not match the identity record: a person must check.")
    rule_ok = 0.0 <= rule.ask_more_min <= rule.auto_handle_min <= 1.0
    if not rule_ok:
        hard_stops.append("invalid_rule")
        reasons.append("The decision rule is not valid (need 0 <= ask_more_min <= auto_handle_min <= 1): a person must check.")

    doc = evidence.document
    fields = (doc.fields if doc is not None else None) or {}  # what OCR read from the ID photo (empty without an OCR engine)
    card_cnic = re.sub(r"\D", "", fields.get("cnic", ""))
    typed_cnic = re.sub(r"\D", "", claim.cnic or getattr(evidence, "account_cnic", None) or "")  # spoken in the claim, or the account's own
    if card_cnic and typed_cnic and card_cnic != typed_cnic:
        hard_stops.append("document_mismatch")
        reasons.append("The ID number read from the ID photo does not match the one given: a person must check.")
    card_name, said_name = _tokens(fields.get("name")), _tokens(claim.claimant_name)
    if card_name and said_name and _align(card_name, said_name)[0] < MATCH_MIN:
        hard_stops.append("document_name_mismatch")
        reasons.append("The name read from the ID photo does not match the name in the claim: a person must check.")
    photo_unclear = doc is not None and (doc.blur_score > BLUR_RETAKE or not doc.format_ok)

    if hard_stops:
        action = DecisionAction.send_to_human
    elif confidence >= rule.auto_handle_min:
        action = DecisionAction.auto_handle
        reasons.append("Confidence %.2f >= %.2f and no red flags" % (confidence, rule.auto_handle_min))
    elif confidence >= rule.ask_more_min:
        action = DecisionAction.ask_more
        reasons.append("Confidence %.2f is between %.2f and %.2f: need more proof" % (confidence, rule.ask_more_min, rule.auto_handle_min))
    else:
        action = DecisionAction.send_to_human
        reasons.append("Confidence %.2f is below %.2f" % (confidence, rule.ask_more_min))

    capped_by = None
    if photo_unclear and action == DecisionAction.auto_handle:
        action, capped_by = DecisionAction.ask_more, "document_unclear"
        reasons.append("The ID photo is unclear: ask for a retake before anything is approved.")
    if action != DecisionAction.send_to_human and len(parts) > 1:
        reasons.append("Weakest signal: %s (%.2f)" % (weakest, confidence))

    match, verdict = evidence.match, evidence.verdict
    inputs: Dict[str, Any] = {  # everything the decision looked at, so it can be replayed and explained later
        "claim_confidence": round(claim.confidence, 4),
        "match_score": round(match.score, 4) if match else None, "match_confidence": round(match.confidence, 4) if match else None,
        "match_found": (match.match_id is not None) if match else None,
        "document_blur": round(doc.blur_score, 4) if doc else None, "document_format_ok": doc.format_ok if doc else None,
        "document_confidence": round(doc.confidence, 4) if doc else None, "document_fields_read": sorted(fields),
        "message_label": verdict.label.value if verdict else None, "message_confidence": round(verdict.confidence, 4) if verdict else None,
        "red_flags_given": list(evidence.red_flags), "mock_failures": list(evidence.mock_failures),
        "payment_step": bool(evidence.payment_step), "ledger_payments": len(evidence.ledger),
    }
    trace: Dict[str, Any] = {
        "combined_confidence": round(confidence, 4), "components": [round(p, 4) for p in parts], "component_names": names,
        "weakest": weakest, "red_flags": flags, "hard_stops": hard_stops, "capped_by": capped_by,
        "thresholds": {"auto_handle_min": rule.auto_handle_min, "ask_more_min": rule.ask_more_min},
        "payment_step": bool(evidence.payment_step), "ledger_payments": len(evidence.ledger),
        "inputs": inputs, "rule_version": rule.version, "model_version": MODEL_VERSION, "final_action": action.value,
    }
    return Decision(action=action, confidence=round(confidence, 4), reasons=reasons, trace=trace, rule_version=rule.version,
                    requires_officer_approval=True, model_version=MODEL_VERSION)
