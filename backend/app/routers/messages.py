from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.fixtures import fixture
from app.services import audit
from contracts.schemas import MessageCheckRequest, MessageCheckResponse

router = APIRouter(tags=["messages"])


@router.post("/messages/check", response_model=MessageCheckResponse)
def check_message(body: MessageCheckRequest, user=Depends(get_current_user)):
    # TODO(Basit): bharosa_ai.classify_message + mocks senders lookup; never auto-block on low confidence.
    audit.log("ai:classify_message", "ai.classify_message", None, {"sender": body.sender}, target=user["user_id"], actor_type="ai")
    return fixture("message_check")
