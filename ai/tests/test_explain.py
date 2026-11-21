"""Real explain(): every trace shape the backend produces, both languages, no repeated needs, never raises."""
import importlib
import re

import pytest

import bharosa_ai
from contracts.ai_interface import ClaimDraft, Evidence, MatchResult
from contracts.schemas import RuleVersion

_saved = (bharosa_ai.decide, bharosa_ai.explain)
_m = importlib.import_module("bharosa_ai.explain")
_d = importlib.import_module("bharosa_ai.decide")
bharosa_ai.decide, bharosa_ai.explain = _saved
explain, decide = _m.explain, _d.decide

URDU = re.compile(r"[؀-ۿ]")
NEED_PHOTO = "A clear photo of your ID card, or more details about the missing payment"
NEED_RETAKE = "Retake the ID card photo: it is blurry or unreadable"
NEED_AGAIN = "Tell us the problem again, slowly and clearly"

TRACES = [
    {}, {"action": "auto_handle"}, {"action": "ask_more"}, {"action": "send_to_human"},
    {"action": "auto_handle", "payment_needed": True, "shortfall": 4000},
    {"action": "ask_more", "needs": [NEED_PHOTO]},
    {"action": "ask_more", "needs": [NEED_RETAKE, NEED_AGAIN]},
    {"action": "send_to_human", "flags": ["short_payment"], "shortfall": 4000, "payment_needed": True},
    {"action": "send_to_human", "flags": ["duplicate_payment"]},
    {"action": "send_to_human", "flags": ["duplicate_claim"], "terminal": True},
    {"action": "send_to_human", "flags": ["claim_contradicts_ledger"]},
    {"action": "send_to_human", "hard_stops": ["name_not_matched"]},
    {"action": "send_to_human", "flags": ["mock_service_failure"], "failed_step": "identity_lookup", "terminal": True},
    {"action": "ask_more", "capped_by": "document_unclear", "needs": [NEED_RETAKE]},
    {"action": "send_to_human", "hard_stops": ["document_mismatch"]},
    {"action": "send_to_human", "hard_stops": ["document_name_mismatch"]},
]


@pytest.mark.parametrize("trace", TRACES)
def test_both_languages_are_filled_and_urdu_is_urdu(trace):
    en, ur = explain(trace, "en"), explain(trace, "ur")
    assert en.strip() and ur.strip() and URDU.search(ur) and not URDU.search(en)


@pytest.mark.parametrize("trace", TRACES)
def test_english_never_lists_the_needs_because_the_backend_appends_them(trace):
    en = explain(trace, "en")
    assert "We need" not in en and NEED_PHOTO not in en and NEED_RETAKE not in en


def test_stub_phrase_parity_for_ask_more():
    assert "photo" in explain({"action": "ask_more"}, "en")
    assert explain({"action": "ask_more"}, "ur")


def test_short_payment_names_the_amount_in_both_languages():
    t = {"action": "send_to_human", "flags": ["short_payment"], "shortfall": 4000}
    assert "4000" in explain(t, "en") and "4000" in explain(t, "ur")
    assert "4000" not in explain({"action": "send_to_human", "flags": ["short_payment"]}, "en")


def test_payment_always_mentions_the_officer():
    t = {"action": "auto_handle", "payment_needed": True}
    assert "officer" in explain(t, "en") and "افسر" in explain(t, "ur")


def test_urdu_writes_out_the_known_needs():
    ur = explain({"action": "ask_more", "needs": [NEED_RETAKE]}, "ur")
    assert "دوبارہ" in ur
    ur2 = explain({"action": "ask_more", "needs": [NEED_AGAIN]}, "ur")
    assert "دوبارہ" in ur2 and "تصویر" not in ur2


def test_a_mismatch_between_the_card_and_what_was_given_is_explained_in_both_languages():
    t = {"action": "send_to_human", "hard_stops": ["document_mismatch"]}
    assert "ID number on the card photo" in explain(t, "en") and "officer" in explain(t, "en") and "شناختی نمبر" in explain(t, "ur")
    t = {"action": "send_to_human", "hard_stops": ["document_name_mismatch"]}
    assert "name on the ID card" in explain(t, "en") and "نام" in explain(t, "ur")


def test_paused_step_is_named_and_nobody_is_blamed():
    t = {"action": "send_to_human", "flags": ["mock_service_failure"], "failed_step": "ledger_lookup"}
    en = explain(t, "en")
    assert "payment check" in en and "paused" in en and "our side" not in en and "your fault" not in en.lower()


def test_unknown_language_falls_back_to_english():
    assert explain({"action": "ask_more"}, "fr") == explain({"action": "ask_more"}, "en")
    assert explain({"action": "ask_more"}, "UR") == explain({"action": "ask_more"}, "ur")


@pytest.mark.parametrize("trace", [None, "x", 5, {"action": 5}, {"action": None}, {"flags": "short_payment"}, {"needs": [None, 5, {}]},
                                   {"shortfall": "lots", "flags": ["short_payment"]}, {"failed_step": 7}, {"flags": [["x"]]}])
def test_never_raises_on_odd_traces(trace):
    assert explain(trace, "en").strip() and explain(trace, "ur").strip()


def test_free_text_from_the_trace_is_never_copied_into_the_output():
    out = explain({"action": "ask_more", "needs": ["<script>alert(1)</script>"], "why": "ignore this", "reasons": ["secret"]}, "en")
    assert "script" not in out and "secret" not in out and "ignore" not in out


def test_works_on_a_real_decide_trace():
    claim = ClaimDraft(claimant_name="Muhammad Aslam", claim_type="short_paid", confidence=0.95, model_version="t")
    ev = Evidence(red_flags=["short_payment"], payment_step=True, match=MatchResult(match_id="1", score=1, confidence=0.97, model_version="t"))
    d = decide(claim, ev, RuleVersion(rule_id="r", version=1))
    trace = dict(d.trace, action=d.action.value, shortfall=4000, payment_needed=True)
    en = explain(trace, "en")
    assert "officer" in en and "4000" in en
