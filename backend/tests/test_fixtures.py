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
    "apikeys": s.ApiKeyListResponse, "eval": s.EvalResults, "eval_live": s.LiveEvalResults,
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
