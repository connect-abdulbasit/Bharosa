"""Server-side auth. Every route (except /health and /auth/login) must use require_role.

Rules enforced here, centrally:
- the user is re-read from the database on every request (role is never trusted from the token);
- auditors are read-only: any non-safe HTTP method is a 403, whatever the route says.
"""
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token
from app.db import get_db
from app.models import User
from contracts.enums import Role

bearer = HTTPBearer(auto_error=False)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def require_role(*roles: Role) -> Callable[..., User]:
    allowed = {r.value if isinstance(r, Role) else str(r) for r in roles}

    def dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        if user.role == Role.auditor.value and request.method not in SAFE_METHODS:
            raise HTTPException(status_code=403, detail="Auditors are read-only")
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Role '%s' is not allowed here" % user.role)
        return user

    return dependency


ANY_ROLE = require_role(*list(Role))
