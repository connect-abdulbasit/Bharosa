"""Row-level access: who may see which citizen's data."""
from typing import Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Family, User
from contracts.enums import Role

STAFF = (Role.officer.value, Role.admin.value, Role.auditor.value)


def linked_citizen_ids(db: Session, helper_id: str) -> Set[str]:
    return set(db.execute(select(Family.citizen_id).where(Family.helper_id == helper_id)).scalars())


def visible_citizen_ids(db: Session, user: User) -> Optional[Set[str]]:
    """None means 'all citizens' (staff). Otherwise the exact set the user may see."""
    if user.role in STAFF:
        return None
    if user.role == Role.helper.value:
        return linked_citizen_ids(db, user.id)
    if user.role == Role.citizen.value:
        return {user.id}
    return set()


def can_access_citizen(db: Session, user: User, citizen_id: str) -> bool:
    ids = visible_citizen_ids(db, user)
    return ids is None or citizen_id in ids


def resolve_citizen(db: Session, user: User, citizen_id: Optional[str]):
    """Which citizen is this request about? Raises 403 if the user may not act for them."""
    from fastapi import HTTPException

    if user.role == Role.citizen.value:
        if citizen_id not in (None, user.id):
            raise HTTPException(status_code=403, detail="You can only act for yourself")
        return user.id
    if user.role == Role.helper.value:
        if not citizen_id:
            raise HTTPException(status_code=422, detail="citizen_id is required for helpers")
        if citizen_id not in linked_citizen_ids(db, user.id):
            raise HTTPException(status_code=403, detail="This citizen is not linked to you")
        return citizen_id
    raise HTTPException(status_code=403, detail="Not allowed")
