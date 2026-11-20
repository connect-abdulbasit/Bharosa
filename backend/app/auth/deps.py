"""Server-side auth. Every route (except /health and /auth/login) must use require_role."""
from typing import Callable

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_token
from app.auth.users import get_user_by_id
from contracts.enums import Role

bearer = HTTPBearer(auto_error=False)
CurrentUser = dict


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = get_user_by_id(payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    # Role comes from the server-side user record, never trusted from the token alone.
    return user


def require_role(*roles: Role) -> Callable[..., CurrentUser]:
    allowed = {r.value if isinstance(r, Role) else str(r) for r in roles}

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if allowed and user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Role '%s' is not allowed here" % user["role"])
        return user

    return dependency


ANY_ROLE = require_role(*list(Role))
