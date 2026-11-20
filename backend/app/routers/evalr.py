from fastapi import APIRouter, Depends

from app.auth import require_role
from app.fixtures import fixture
from contracts.enums import Role
from contracts.schemas import EvalResults

router = APIRouter(tags=["eval"])


@router.get("/eval", response_model=EvalResults)
def evaluation(user=Depends(require_role(Role.officer, Role.admin, Role.auditor))):
    # TODO(Basit): serve ai/eval_results.json produced by Ali's run_eval.py.
    return fixture("eval")
