import bharosa_ai
from contracts.ai_interface import ClaimDraft, ExtractionError
from tests.conftest import auth


def test_refiling_after_an_unclear_claim_is_not_a_duplicate(client, mocks, monkeypatch):
    """'Tell us the problem again' must be answerable: the unclear first attempt has no month, so it never blocks the second."""
    h = auth(client, "citizen06")
    monkeypatch.setattr(bharosa_ai, "extract_claim", lambda t: ExtractionError(
        error="no_claim_found", reason="no payment problem was mentioned", missing_fields=["claim_type"], confidence=0.0, model_version="t"))
    first = client.post("/claims", json={"transcript": "hello what are you doing"}, headers=h).json()
    assert first["status"] == "needs_more_proof"
    monkeypatch.setattr(bharosa_ai, "extract_claim", lambda t: ClaimDraft(
        claimant_name="Mohammad Aslam", claim_type="missing", amount_claimed_pkr=12000, period="2026-10", confidence=0.7, model_version="t"))
    second = client.post("/claims", json={"transcript": "mera naam Mohammad Aslam hai. Mujhe paisay nahi mile"}, headers=h).json()
    assert "duplicate_claim" not in (second["decision"]["trace"].get("flags") or [])
    assert second["status"] == "needs_more_proof"
