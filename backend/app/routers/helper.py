from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from contracts.enums import Role
from contracts.schemas import HelperFamiliesResponse

router = APIRouter(tags=["helper"])


@router.get("/helper/families", response_model=HelperFamiliesResponse)
def families(user=Depends(require_role(Role.helper))):
    # TODO(Basit): per-family consent; a helper may only act for families that consented.
    return fixture("helper_families")
