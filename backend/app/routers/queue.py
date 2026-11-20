from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from contracts.enums import Role
from contracts.schemas import QueueResponse

router = APIRouter(tags=["queue"])


@router.get("/queue", response_model=QueueResponse)
def review_queue(user=Depends(require_role(Role.officer, Role.admin))):
    # TODO(Basit): real queue, sorted by risk desc then confidence asc.
    return fixture("queue")
