"""Integration tests: the pipeline with AI_MODE=real. Run with `make test-integration`.
They are deselected by default and SKIP (with a reason) until every real AI function is implemented (TODO(Ali))."""
import importlib
import os

import pytest

from contracts.ai_interface import (ClaimDraft, Decision, DocumentReading, Evidence, ExtractionError, MatchResult, MessageVerdict)
from contracts.schemas import PersonRecord, RuleVersion
from tests.conftest import auth, make_image

pytestmark = pytest.mark.integration

RULE = RuleVersion(rule_id="r", version=1)
PERSON = PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", aliases=["Mohammad Aslam"])
DRAFT = ClaimDraft(claimant_name="Muhammad Aslam", claim_type="missing", amount_claimed_pkr=12000, period="2026-10", confidence=0.9, model_version="t")


def probes(ai):
    return {
        "classify_message": lambda: ai.classify_message("Your stipend is ready", "9090"),
        "match_person": lambda: ai.match_person("Mohammad Aslam", None, [PERSON]),
        "extract_claim": lambda: ai.extract_claim("mujhe is mahine ke paisay nahi mile"),
        "read_document": lambda: ai.read_document(make_image(600, 400, "JPEG")),
        "decide": lambda: ai.decide(DRAFT, Evidence(), RULE),
        "explain": lambda: ai.explain({"action": "ask_more"}, "en"),
    }


@pytest.fixture()
def real_ai():
    import bharosa_ai

    previous = os.environ.get("AI_MODE")
    os.environ["AI_MODE"] = "real"
    importlib.reload(bharosa_ai)  # the package picks stub/real at import time
    try:
        missing = []
        for name, call in probes(bharosa_ai).items():
            try:
                call()
            except NotImplementedError:
                missing.append(name)
        if missing:
            pytest.skip("real AI is not implemented yet (TODO(Ali)): %s" % ", ".join(missing))
        assert bharosa_ai.AI_MODE == "real"
        yield bharosa_ai
    finally:
        if previous is None:
            os.environ.pop("AI_MODE", None)
        else:
            os.environ["AI_MODE"] = previous
        importlib.reload(bharosa_ai)  # back to the stub for every other test


def test_real_functions_honour_the_contract(real_ai):
    out = {name: call() for name, call in probes(real_ai).items()}
    assert isinstance(out["classify_message"], MessageVerdict) and isinstance(out["match_person"], MatchResult)
    assert isinstance(out["extract_claim"], (ClaimDraft, ExtractionError)) and isinstance(out["read_document"], DocumentReading)
    assert isinstance(out["decide"], Decision) and isinstance(out["explain"], str) and out["explain"].strip()
    for name in ("classify_message", "match_person", "extract_claim", "read_document", "decide"):
        res = out[name]
        assert 0.0 <= res.confidence <= 1.0, name           # every AI output carries a confidence...
        assert res.model_version and not res.model_version.startswith("stub"), name  # ...and says which (real) model made it


def test_real_decide_never_auto_handles_red_flags_and_reads_thresholds_from_the_rule(real_ai):
    flagged = real_ai.decide(DRAFT, Evidence(red_flags=["short_payment"]), RULE)
    assert flagged.action.value != "auto_handle"
    strict = real_ai.decide(DRAFT, Evidence(), RuleVersion(rule_id="r", version=2, auto_handle_min=1.0, ask_more_min=0.99))
    assert strict.action.value != "auto_handle" and strict.rule_version == 2  # thresholds are not hard-coded
    assert real_ai.decide(DRAFT, Evidence(payment_step=True), RULE).requires_officer_approval is True


def test_pipeline_runs_end_to_end_with_real_ai(real_ai, client, db, mocks):
    from sqlalchemy import select

    from app.models import AuditLog

    r = client.post("/claims", json={"transcript": "mujhe is mahine ke paisay nahi mile"}, headers=auth(client, "citizen05"))
    assert r.status_code == 202
    b = r.json()
    assert b["status"] in ("needs_more_proof", "with_officer", "approved") and b["decision"]["rule_version"] == 1
    assert b["explanation_ur"] and b["explanation_en"]
    assert not any("internal error" in s["detail"] for s in b["pipeline_steps"])  # the real AI did not crash a step
    ai_rows = db.execute(select(AuditLog).where(AuditLog.entity_id == b["case_id"], AuditLog.actor_type == "ai")).scalars().all()
    assert ai_rows and all(x.after["model_version"] and x.after["confidence"] is not None for x in ai_rows)
    if b["decision"]["action"] == "auto_handle":
        assert b["status"] != "approved"  # a payment still needs an officer


def test_real_scam_check_through_the_api(real_ai, client, mocks):
    b = client.post("/messages/check", json={"text": "Pay Rs 500 fee at http://bit.ly/x to receive relief", "sender": "9O9O"}, headers=auth(client, "citizen")).json()
    assert b["label"] in ("scam", "unsure") and b["label"] != "genuine" and 0 <= b["confidence"] <= 1 and b["model_version"]
