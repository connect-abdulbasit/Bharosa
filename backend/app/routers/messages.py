from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.models import User
from app.services import audit, scam
from app.services.mocks_client import get_mocks_client
from contracts.enums import Role
from contracts.schemas import MessageCheckRequest, MessageCheckResponse

router = APIRouter(tags=["messages"])


@router.post("/messages/check", response_model=MessageCheckResponse)
def check_message(body: MessageCheckRequest, user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Classify a message and verify its sender against the official list. Each check is stored (text hash only)."""
    out = scam.check_message(db, get_mocks_client(), body.text, body.sender, body.area)
    audit.log(db, "ai", "ai:classify_message", "ai.classify_message", "message", scam.text_hash(body.text)[:16],
              after={"label": out["label"], "confidence": out["confidence"], "sender": body.sender[:60],
                     "official_sender": out["official_sender"], "model_version": out["model_version"], "requested_by": user.id})
    db.commit()
    return out
