"""In-app notifications for the signed-in citizen (messages created by the notifications service when a case status changes)."""
from fastapi import APIRouter, Depends

from app.auth import require_role
from app.models import User
from app.routing import CompactRoute
from app.services import outbound
from contracts.enums import Role
from contracts.schemas import NotificationsResponse

router = APIRouter(tags=["notifications"], route_class=CompactRoute)


@router.get("/me/notifications", response_model=NotificationsResponse, summary="My in-app messages (Urdu + English)")
def my_notifications(user: User = Depends(require_role(Role.citizen, Role.helper))):
    """Only the caller's own messages. Empty when the notifications service is off or unreachable (never an error)."""
    return {"items": outbound.inbox(user)}
