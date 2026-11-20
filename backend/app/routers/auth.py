from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import ANY_ROLE, require_role
from app.auth.jwt import create_token
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.db import get_db
from app.models import User
from app.services import audit
from contracts.enums import Role
from contracts.schemas import LoginRequest, Me, TokenResponse
from pydantic import BaseModel

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(or_(User.username == body.username, User.phone == body.username))).scalars().first()
    if user is None or not verify_password(body.password, user.password_hash):
        audit.log(db, "system", None, "auth.login_failed", "user", user.id if user else None,
                  after={"username": body.username[:50]})
        db.commit()
        raise HTTPException(status_code=401, detail="Wrong username or password")
    audit.log(db, "user", user.id, "auth.login", "user", user.id, after={"role": user.role})
    db.commit()
    return TokenResponse(access_token=create_token(user.id, user.role), role=user.role, expires_in=settings.JWT_EXPIRES_SECONDS)


@router.get("/me", response_model=Me)
def me(user: User = Depends(ANY_ROLE)):
    return Me(user_id=user.id, username=user.username, display_name=user.name, role=user.role, language="ur")


class SetPin(BaseModel):
    pin: str
    password: str  # the account password confirms it is really the citizen


@router.post("/me/pin")
def set_pin(body: SetPin, user: User = Depends(require_role(Role.citizen)), db: Session = Depends(get_db)):
    """A citizen sets/changes the 4-digit PIN a helper needs to grant consent on their behalf."""
    if not (body.pin.isdigit() and len(body.pin) == 4):
        raise HTTPException(status_code=422, detail="PIN must be exactly 4 digits")
    if not verify_password(body.password, user.password_hash):
        audit.log(db, "user", user.id, "user.pin_change_denied", "user", user.id)
        db.commit()
        raise HTTPException(status_code=403, detail="Wrong password")
    user.pin_hash = hash_password(body.pin)
    audit.log(db, "user", user.id, "user.pin_set", "user", user.id, after={"pin_set": True})  # never the PIN itself
    db.commit()
    return {"ok": True}
