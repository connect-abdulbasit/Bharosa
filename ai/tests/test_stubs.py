import os

os.environ["AI_MODE"] = "stub"

import bharosa_ai  # noqa: E402
from contracts.ai_interface import (  # noqa: E402
    ClaimDraft, Decision, DocumentReading, Evidence, ExtractionError, MatchResult, MessageVerdict)
from contracts.enums import DecisionAction, MessageLabel  # noqa: E402
from contracts.schemas import PersonRecord, RuleVersion  # noqa: E402

RULE = RuleVersion(rule_id="r1", version=3)
CANDS = [
    PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", aliases=["Mohammad Aslam"]),
    PersonRecord(cnic="0000042101002", full_name="Fatima Noor"),
]


def _claim(conf=0.95):
    return ClaimDraft(claimant_name="Muhammad Aslam", claim_type="missing", confidence=conf, model_version="t")


def test_mode_is_stub():
    assert bharosa_ai.AI_MODE == "stub"


def test_classify_scam_and_genuine():
    scam = bharosa_ai.classify_message("Pay fee at http://bit.ly/x to get relief", "SAHARA-INFO")
    assert isinstance(scam, MessageVerdict) and scam.label == MessageLabel.scam and scam.model_version
    ok = bharosa_ai.classify_message("Your stipend is ready", "9090")
    assert ok.label == MessageLabel.genuine


def test_match_person_handles_spelling_variants():
    m = bharosa_ai.match_person("Mohammad Aslam", None, CANDS)
    assert isinstance(m, MatchResult) and m.match_id == "0000042101001" and m.model_version


def test_match_person_no_match_returns_none():
    m = bharosa_ai.match_person("Totally Different", None, CANDS)
    assert m.match_id is None


def test_extract_claim_ok_and_error():
    assert isinstance(bharosa_ai.extract_claim("mujhe paisay kam mile hain"), ClaimDraft)
    assert isinstance(bharosa_ai.extract_claim("hi"), ExtractionError)


def test_read_document():
    r = bharosa_ai.read_document(b"x" * 500)
    assert isinstance(r, DocumentReading) and r.format_ok and r.model_version
    assert bharosa_ai.read_document(b"").format_ok is False


def test_decide_thresholds_and_red_flags():
    hi = bharosa_ai.decide(_claim(0.95), Evidence(), RULE)
    assert isinstance(hi, Decision) and hi.action == DecisionAction.auto_handle and hi.rule_version == 3
    mid = bharosa_ai.decide(_claim(0.75), Evidence(), RULE)
    assert mid.action == DecisionAction.ask_more
    low = bharosa_ai.decide(_claim(0.4), Evidence(), RULE)
    assert low.action == DecisionAction.send_to_human
    flagged = bharosa_ai.decide(_claim(0.99), Evidence(red_flags=["short_payment"]), RULE)
    assert flagged.action == DecisionAction.send_to_human


def test_decide_reads_thresholds_from_rule():
    strict = RuleVersion(rule_id="r1", version=4, auto_handle_min=0.99, ask_more_min=0.9)
    assert bharosa_ai.decide(_claim(0.95), Evidence(), strict).action == DecisionAction.ask_more


def test_payment_step_requires_officer():
    d = bharosa_ai.decide(_claim(0.99), Evidence(payment_step=True), RULE)
    assert d.requires_officer_approval is True


def test_explain_both_languages():
    assert bharosa_ai.explain({"action": "ask_more"}, "ur")
    assert "photo" in bharosa_ai.explain({"action": "ask_more"}, "en")
