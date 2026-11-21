"""Every platform fixture must validate against contracts/schemas.py, and every fixture must be used."""
import json

import pytest

from app.config import settings
from contracts import schemas as s

MODELS = {
    "auth_login": s.TokenResponse, "me": s.Me, "cases_list": s.CaseListResponse, "case_create": s.CaseDetail,
    "case_detail": s.CaseDetail, "case_assign": s.CaseDetail, "case_escalate": s.CaseDetail,
    "case_decide": s.CaseDetail, "case_close": s.CaseDetail, "claim_create": s.ClaimResponse,
    "message_check": s.MessageCheckResponse, "document_upload": s.DocumentResponse,
    "rules_list": s.RuleListResponse, "rule_versions": s.RuleVersionsResponse,
    "consent_list": s.ConsentListResponse, "consent_withdraw": s.ConsentRecord,
    "audit_list": s.AuditListResponse, "queue": s.QueueResponse, "helper_families": s.HelperFamiliesResponse,
    "apikeys": s.ApiKeyListResponse, "eval": s.EvalResults, "eval_live": s.LiveEvalResults, "scam_map": s.ScamMapResponse, "demo_people": s.DemoPeople,
}


@pytest.mark.parametrize("name,model", MODELS.items())
def test_fixture_matches_schema(name, model):
    model(**json.loads((settings.FIXTURES_DIR / (name + ".json")).read_text(encoding="utf-8")))


def test_no_unlisted_fixtures():
    on_disk = {p.stem for p in settings.FIXTURES_DIR.glob("*.json")}
    assert on_disk == set(MODELS)


def test_fixture_cnics_are_fake():
    text = "".join(p.read_text(encoding="utf-8") for p in settings.FIXTURES_DIR.glob("*.json"))
    assert "00000" in text


def test_demo_people_invariants():
    """The shared demo file must stay safe and consistent: fake CNICs, unique ids, known agents, no clash with the mocks' own 5 people."""
    data = s.DemoPeople(**json.loads((settings.FIXTURES_DIR / "demo_people.json").read_text(encoding="utf-8")))
    people = data.people
    assert [p.n for p in people] == list(range(1, len(people) + 1)) and len(people) == 8
    for field in ("username", "user_id", "cnic", "key"):
        values = [getattr(p, field) for p in people]
        assert len(values) == len(set(values)), field
    mocks_seed = {"0000042101001", "0000042101002", "0000042101003", "0000042101004", "0000042101005"}
    for p in people:
        assert len(p.cnic) == 13 and p.cnic.isdigit() and p.cnic.startswith("00000") and p.cnic not in mocks_seed
        assert p.expected_status and p.expected_action and p.request
    agents = {a.agent_id for a in data.agents}
    assert "agent-099" in agents and all(pay.agent_id in agents for p in people for pay in p.payments)
    assert "9090" in data.official_senders and not set(data.official_senders) & set(data.lookalike_senders)
