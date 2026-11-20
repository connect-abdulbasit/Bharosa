from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.auth.jwt import create_token
from app.auth.passwords import verify_password
from app.auth.users import get_user_by_username
from app.config import settings
from app.services import audit
from contracts.schemas import LoginRequest, Me, TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = get_user_by_username(body.username)
    if user is None or not verify_password(body.password, user["password_hash"]):
        audit.log(body.username, "auth.login_failed", None, None, target=body.username)
        raise HTTPException(status_code=401, detail="Wrong username or password")
    audit.log(user["user_id"], "auth.login", None, {"role": user["role"]}, target=user["user_id"])
    return TokenResponse(access_token=create_token(user["user_id"], user["role"]), role=user["role"],
                         expires_in=settings.JWT_EXPIRES_SECONDS)


@router.get("/me", response_model=Me)
def me(user=Depends(get_current_user)):
    return Me(**{k: user[k] for k in ("user_id", "username", "display_name", "role", "language")})
