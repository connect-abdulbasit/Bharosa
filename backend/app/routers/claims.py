from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import ClaimCreate, ClaimResponse

router = APIRouter(tags=["claims"])


@router.post("/claims", response_model=ClaimResponse)
def create_claim(body: ClaimCreate, user=Depends(require_role(Role.citizen, Role.helper))):
    # TODO(Basit): call services.pipeline.run_claim_pipeline (resumable steps, consent first).
    out = fixture("claim_create")
    audit.log(user["user_id"], "claim.create", None, {"claim_id": out["claim_id"]}, target=out["claim_id"])
    return out
