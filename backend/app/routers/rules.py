from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import RuleListResponse, RuleVersion, RuleVersionCreate, RuleVersionsResponse

router = APIRouter(tags=["rules"])
READERS = (Role.officer, Role.admin, Role.auditor)


@router.get("/rules", response_model=RuleListResponse)
def list_rules(user=Depends(require_role(*READERS))):
    return fixture("rules_list")


@router.get("/rules/{rule_id}/versions", response_model=RuleVersionsResponse)
def list_versions(rule_id: str, user=Depends(require_role(*READERS))):
    return fixture("rule_versions")


@router.post("/rules/{rule_id}/versions", response_model=RuleVersion)
def create_version(rule_id: str, body: RuleVersionCreate, user=Depends(require_role(Role.admin))):
    # TODO(Basit): validate json-logic, insert immutable new version, no redeploy needed.
    out = dict(fixture("rule_versions")["versions"][0], version=4, auto_handle_min=body.auto_handle_min,
               ask_more_min=body.ask_more_min, red_flags=body.red_flags, note=body.note, created_by=user["user_id"])
    audit.log(user["user_id"], "rule.new_version", None, {"rule_id": rule_id, "version": 4}, target=rule_id)
    return out
