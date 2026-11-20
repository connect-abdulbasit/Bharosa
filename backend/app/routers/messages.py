from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.fixtures import fixture
from app.models import User
from app.services import audit
from contracts.enums import Role
from contracts.schemas import MessageCheckRequest, MessageCheckResponse

router = APIRouter(tags=["messages"])


@router.post("/messages/check", response_model=MessageCheckResponse)
def check_message(body: MessageCheckRequest, user: User = Depends(require_role(Role.citizen, Role.helper, Role.officer, Role.admin)),
                  db: Session = Depends(get_db)):
    # TODO(Basit): bharosa_ai.classify_message + mocks senders lookup; never auto-block on low confidence.
    audit.log(db, "ai", "classify_message", "ai.classify_message", "message", None, after={"sender": body.sender, "requested_by": user.id})
    db.commit()
    return fixture("message_check")
