"""Rate limiting (slowapi). Limits come from settings so they can be tuned without code changes:
  - default (per client IP) for every route, stricter for /auth/login, and per API key on the public routes."""
import hashlib
from typing import Optional

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings


def client_ip(request: Request) -> str:
    """Behind a proxy (Render/Railway) the real client is the first X-Forwarded-For entry. Only trusted when
    TRUST_PROXY=1, otherwise the header could be forged to dodge the limit."""
    if settings.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def key_or_ip(request: Request) -> str:
    raw: Optional[str] = request.headers.get("x-api-key")
    if raw:
        return "key:" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    return client_ip(request)


limiter = Limiter(key_func=client_ip, default_limits=[lambda: settings.DEFAULT_RATE_LIMIT], headers_enabled=False)
