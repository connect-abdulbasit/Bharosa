"""TODO(Basit): real case management. Currently returns fixtures; mutations write to the audit log."""
from fastapi import APIRouter, Depends

from app.auth import get_current_user, require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import (AssignRequest, CaseCreate, CaseDetail, CaseListResponse, CloseRequest,
                               EscalateRequest, OfficerDecision)

router = APIRouter(tags=["cases"])


@router.get("/cases", response_model=CaseListResponse)
def list_cases(user=Depends(get_current_user)):
    # TODO(Basit): citizens see own cases only; helpers see their families'; officers see assigned/queue.
    return fixture("cases_list")


@router.post("/cases", response_model=CaseDetail)
def create_case(body: CaseCreate, user=Depends(require_role(Role.citizen, Role.helper))):
    out = fixture("case_create")
    audit.log(user["user_id"], "case.create", None, {"id": out["id"], "status": out["status"]}, target=out["id"])
    return out


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, user=Depends(get_current_user)):
    return fixture("case_detail")


@router.post("/cases/{case_id}/assign", response_model=CaseDetail)
def assign(case_id: str, body: AssignRequest, user=Depends(require_role(Role.officer, Role.admin))):
    audit.log(user["user_id"], "case.assign", None, {"assigned_to": body.officer_id}, target=case_id)
    return fixture("case_assign")


@router.post("/cases/{case_id}/escalate", response_model=CaseDetail)
def escalate(case_id: str, body: EscalateRequest, user=Depends(require_role(Role.helper, Role.officer))):
    audit.log(user["user_id"], "case.escalate", None, {"reason": body.reason}, target=case_id)
    return fixture("case_escalate")


@router.post("/cases/{case_id}/decide", response_model=CaseDetail)
def decide(case_id: str, body: OfficerDecision, user=Depends(require_role(Role.officer))):
    # Payment steps always need an officer: only Role.officer may decide.
    audit.log(user["user_id"], "case.decide", None, {"action": body.action, "note": body.note}, target=case_id)
    return fixture("case_decide")


@router.post("/cases/{case_id}/close", response_model=CaseDetail)
def close(case_id: str, body: CloseRequest, user=Depends(require_role(Role.officer, Role.admin))):
    audit.log(user["user_id"], "case.close", None, {"resolution": body.resolution}, target=case_id)
    return fixture("case_close")
