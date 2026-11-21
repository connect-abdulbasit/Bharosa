"""Real decide(): thresholds from the rule, hard stops, weakest link, determinism, JSON-safe trace.

Imported by module path: the package namespace holds the stub function with the same name (see test_contract.py).
"""
import importlib
import json

import pytest

from contracts.ai_interface import ClaimDraft, DocumentReading, Evidence, MatchResult, MessageVerdict
from contracts.enums import DecisionAction, MessageLabel
from contracts.schemas import RuleVersion

import bharosa_ai  # noqa: E402

_saved = bharosa_ai.decide
decide = importlib.import_module("bharosa_ai.decide").decide
bharosa_ai.decide = _saved  # importing the submodule rebinds the package attribute: put the function back

RULE = RuleVersion(rule_id="r1", version=3)  # 0.90 / 0.60
AUTO, ASK, HUMAN = DecisionAction.auto_handle, DecisionAction.ask_more, DecisionAction.send_to_human
RANK = {HUMAN: 0, ASK: 1, AUTO: 2}


def claim(conf=0.95):
    return ClaimDraft(claimant_name="Muhammad Aslam", claim_type="missing", confidence=conf, model_version="t")


def match(conf=0.97, match_id="0000042101001"):
    return MatchResult(match_id=match_id, score=conf, confidence=conf, model_version="t")


def photo(blur=0.1, ok=True, conf=0.8):
    return DocumentReading(fields={}, blur_score=blur, format_ok=ok, confidence=conf, model_version="t")


def test_three_actions_from_the_rule_thresholds():
    assert decide(claim(0.95), Evidence(), RULE).action == AUTO
    assert decide(claim(0.75), Evidence(), RULE).action == ASK
    assert decide(claim(0.40), Evidence(), RULE).action == HUMAN


def test_boundaries_are_inclusive():
    assert decide(claim(0.90), Evidence(), RULE).action == AUTO
    assert decide(claim(0.8999), Evidence(), RULE).action == ASK
    assert decide(claim(0.60), Evidence(), RULE).action == ASK
    assert decide(claim(0.5999), Evidence(), RULE).action == HUMAN


@pytest.mark.parametrize("auto,ask", [(0.99, 0.9), (0.8, 0.5), (0.5, 0.5), (1.0, 0.99), (0.7, 0.0)])
def test_thresholds_come_from_the_rule_never_hard_coded(auto, ask):
    rule = RuleVersion(rule_id="r", version=9, auto_handle_min=auto, ask_more_min=ask)
    assert decide(claim(auto), Evidence(), rule).action == AUTO
    if ask < auto:
        assert decide(claim(auto - 0.001), Evidence(), rule).action == (ASK if auto - 0.001 >= ask else HUMAN)
    d = decide(claim(0.7), Evidence(), rule)
    assert d.trace["thresholds"] == {"auto_handle_min": auto, "ask_more_min": ask} and d.rule_version == 9


def test_rule_logic_is_ignored_on_purpose():
    rule = RuleVersion(rule_id="r", version=2, auto_handle_min=0.99, ask_more_min=0.9, logic={"if": [True, "auto_handle", "auto_handle"]})
    assert decide(claim(0.95), Evidence(), rule).action == ASK


@pytest.mark.parametrize("ev", [
    Evidence(red_flags=["short_payment"]),
    Evidence(red_flags=["duplicate_payment", "lookalike_sender"]),
    Evidence(mock_failures=["identity"]),
    Evidence(match=match(0.99, match_id=None)),
])
def test_hard_stops_never_auto_handle_whatever_the_confidence(ev):
    d = decide(claim(1.0), ev, RULE)
    assert d.action == HUMAN and d.trace["hard_stops"]


def test_failed_service_check_is_reported_as_a_flag():
    d = decide(claim(1.0), Evidence(mock_failures=["identity"]), RULE)
    assert "mock_service_failure" in d.trace["red_flags"]


def test_unmatched_name_is_a_hard_stop_with_its_own_reason():
    d = decide(claim(1.0), Evidence(match=match(0.99, match_id=None)), RULE)
    assert "name_not_matched" in d.trace["hard_stops"] and any("name" in r for r in d.reasons)


@pytest.mark.parametrize("auto,ask", [(0.5, 0.9), (1.2, 0.5), (0.9, -0.1)])
def test_invalid_rule_fails_safe_to_a_person(auto, ask):
    d = decide(claim(1.0), Evidence(), RuleVersion(rule_id="r", version=1, auto_handle_min=auto, ask_more_min=ask))
    assert d.action == HUMAN and "invalid_rule" in d.trace["hard_stops"]


def test_weakest_link_sets_the_confidence():
    d = decide(claim(0.95), Evidence(match=match(0.7), document=photo(conf=0.95)), RULE)
    assert d.confidence == 0.7 and d.action == ASK
    assert d.trace["weakest"] == "match" and d.trace["component_names"] == ["claim", "match", "document"]
    verdict = MessageVerdict(label=MessageLabel.scam, confidence=0.55, reasons=[], model_version="t")
    assert decide(claim(0.95), Evidence(verdict=verdict), RULE).trace["weakest"] == "message"


def test_unclear_photo_is_capped_at_ask_more():
    for bad in (photo(blur=0.8, conf=0.99), photo(ok=False, conf=0.99)):
        d = decide(claim(0.99), Evidence(match=match(0.99), document=bad), RULE)
        assert d.action == ASK and d.trace["capped_by"] == "document_unclear"
    assert decide(claim(0.99), Evidence(match=match(0.99), document=photo(blur=0.5, conf=0.99)), RULE).action == AUTO  # 0.5 is still readable
    assert decide(claim(0.3), Evidence(document=photo(blur=0.9, conf=0.99)), RULE).action == HUMAN  # the cap never makes it softer


def test_monotonic_in_confidence():
    ev = Evidence(match=match(0.99))
    ranks = [RANK[decide(claim(i / 100), ev, RULE).action] for i in range(0, 101)]
    assert ranks == sorted(ranks)


def test_no_auto_handle_with_any_stop_over_a_grid():
    stops = [Evidence(red_flags=["x"]), Evidence(mock_failures=["m"]), Evidence(match=match(1.0, match_id=None))]
    for ev in stops:
        for i in range(0, 101):
            assert decide(claim(i / 100), ev, RULE).action == HUMAN


def test_payment_step_goes_into_the_trace_and_officer_approval_is_always_required():
    d = decide(claim(0.99), Evidence(payment_step=True), RULE)
    assert d.requires_officer_approval is True and d.trace["payment_step"] is True
    assert decide(claim(0.99), Evidence(), RULE).requires_officer_approval is True


def test_deterministic_and_json_safe():
    ev = Evidence(match=match(0.8), document=photo(), red_flags=["short_payment"], payment_step=True)
    a, b = decide(claim(0.9), ev, RULE), decide(claim(0.9), ev, RULE)
    assert a.model_dump() == b.model_dump()
    assert json.loads(json.dumps(a.trace)) == a.trace


def test_the_trace_records_inputs_each_step_rule_and_model_version_and_the_final_action():
    verdict = MessageVerdict(label=MessageLabel.scam, confidence=0.9, reasons=[], model_version="t")
    ev = Evidence(match=match(0.97), document=photo(blur=0.2, conf=0.75), verdict=verdict, red_flags=["short_payment"],
                  mock_failures=["identity"], payment_step=True)
    d = decide(claim(0.9), ev, RULE)
    t = d.trace
    assert t["rule_version"] == 3 and t["model_version"] == "decide-rules-1.0" and t["final_action"] == d.action.value == "send_to_human"
    assert t["components"] == [0.9, 0.97, 0.75, 0.9] and t["component_names"] == ["claim", "match", "document", "message"]
    assert t["inputs"] == {
        "claim_confidence": 0.9, "match_score": 0.97, "match_confidence": 0.97, "match_found": True, "document_blur": 0.2,
        "document_format_ok": True, "document_confidence": 0.75, "document_fields_read": [], "message_label": "scam", "message_confidence": 0.9,
        "red_flags_given": ["short_payment"], "mock_failures": ["identity"], "payment_step": True, "ledger_payments": 0}
    assert json.loads(json.dumps(t)) == t


def test_trace_inputs_are_none_for_evidence_that_was_not_given():
    inputs = decide(claim(0.7), Evidence(), RULE).trace["inputs"]
    assert inputs["claim_confidence"] == 0.7 and inputs["match_score"] is None and inputs["match_found"] is None
    assert inputs["document_blur"] is None and inputs["message_label"] is None and inputs["red_flags_given"] == []


CARD = {"cnic": "0000042101001", "name": "Muhammad Aslam", "father_name": "Abdul Rehman", "date_of_birth": "1984-03-12"}


def read_card(conf=0.99, **over):
    """A card read by OCR. The default confidence is high so these tests isolate the mismatch logic (a real read is capped at 0.85)."""
    return DocumentReading(fields=dict(CARD, **over), blur_score=0.1, format_ok=True, confidence=conf, model_version="doc-ocr-test-1.0")


def test_a_real_ocr_read_can_never_reach_the_auto_handle_line_on_its_own():
    d = decide(claim(1.0), Evidence(match=match(0.99), document=read_card(conf=0.85)), RULE)
    assert d.action == ASK and d.trace["hard_stops"] == []


def test_a_card_that_agrees_with_the_claim_is_no_problem():
    c = ClaimDraft(claimant_name="Mohammad Aslam", cnic="00000-4210100-1", claim_type="missing", confidence=0.95, model_version="t")
    d = decide(c, Evidence(match=match(0.97), document=read_card()), RULE)
    assert d.action == AUTO and d.trace["hard_stops"] == [] and d.trace["inputs"]["document_fields_read"] == ["cnic", "date_of_birth", "father_name", "name"]


def test_a_cnic_on_the_card_that_differs_from_the_one_given_is_a_hard_stop():
    c = ClaimDraft(claimant_name="Muhammad Aslam", cnic="0000042101002", claim_type="missing", confidence=1.0, model_version="t")
    d = decide(c, Evidence(match=match(0.99), document=read_card()), RULE)
    assert d.action == HUMAN and "document_mismatch" in d.trace["hard_stops"] and any("ID number" in r for r in d.reasons)


def test_the_account_cnic_is_used_when_the_contract_has_it_and_ignored_when_not():
    ev = Evidence(match=match(0.99), document=read_card())
    c = claim(1.0)
    assert decide(c, ev, RULE).action == AUTO                                           # no typed CNIC at all: nothing to compare
    object.__setattr__(ev, "account_cnic", "0000042101999")                            # what an additive contract field would carry
    assert "document_mismatch" in decide(c, ev, RULE).trace["hard_stops"]
    object.__setattr__(ev, "account_cnic", "00000-4210100-1")
    assert "document_mismatch" not in decide(c, ev, RULE).trace["hard_stops"]


def test_a_name_on_the_card_that_differs_from_the_claim_is_a_hard_stop():
    d = decide(claim(1.0), Evidence(match=match(0.99), document=read_card(name="Fatima Noor")), RULE)
    assert d.action == HUMAN and d.trace["hard_stops"] == ["document_name_mismatch"] and any("name read" in r for r in d.reasons)


def test_a_spelling_difference_between_card_and_claim_is_not_a_mismatch():
    for card_name in ("Mohammad Aslam", "MUHAMMAD ASLAM", "Aslam Muhammad", "Mr Muhammad Aslam"):
        d = decide(claim(1.0), Evidence(match=match(0.99), document=read_card(name=card_name)), RULE)
        assert "document_name_mismatch" not in d.trace["hard_stops"], card_name


def test_without_ocr_fields_nothing_changes():
    plain = DocumentReading(fields={}, blur_score=0.1, format_ok=True, confidence=0.75, model_version="doc-quality-1.0")
    c = ClaimDraft(claimant_name="Muhammad Aslam", cnic="0000042101002", claim_type="missing", confidence=0.95, model_version="t")
    assert decide(c, Evidence(match=match(0.97), document=plain), RULE).trace["hard_stops"] == []


def test_the_existing_trace_keys_are_unchanged():  # the backend and explain() read these
    keys = {"combined_confidence", "components", "component_names", "weakest", "red_flags", "hard_stops", "capped_by", "thresholds",
            "payment_step", "ledger_payments"}
    assert keys <= set(decide(claim(0.7), Evidence(), RULE).trace)


def test_metadata_and_reasons_are_filled():
    d = decide(claim(0.95), Evidence(), RULE)
    assert d.rule_version == 3 and d.reasons and d.model_version == "decide-rules-1.0" and len(d.model_version) <= 40
    assert any("0.95" in r for r in d.reasons)  # the numbers are in the reasons
