from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from contracts.enums import Role
from contracts.schemas import AuditListResponse

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditListResponse)
def list_audit(user=Depends(require_role(Role.auditor, Role.admin))):
    # TODO(Basit): read the append-only audit_log table with filters (actor, action, target, date).
    return fixture("audit_list")
