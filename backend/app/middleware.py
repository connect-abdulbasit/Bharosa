"""Request context (id, role, latency, access log) and ETag for cheap polling on weak connections."""
import hashlib
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services import audit

access_log = logging.getLogger("bharosa.access")
ETAG_PATHS = re.compile(r"^/(cases/[^/]+|queue|claims/[^/]+/progress|public/cases/[^/]+/status)$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Tags every request with an id (X-Request-ID in and out), times it, and writes ONE JSON access-log line."""

    async def dispatch(self, request: Request, call_next):
        rid = (request.headers.get("x-request-id") or uuid.uuid4().hex)[:64]
        request.state.request_id = rid
        request.state.role = "anonymous"
        token = audit.request_id_var.set(rid)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            latency = round((time.perf_counter() - started) * 1000, 1)
            level = logging.DEBUG if request.url.path == "/health" else logging.INFO
            access_log.log(level, "request", extra={"method": request.method, "path": request.url.path, "status": status,
                                                    "latency_ms": latency, "role": getattr(request.state, "role", "anonymous")})
            audit.request_id_var.reset(token)


def _matches(header: str, etag: str) -> bool:
    bare = etag.replace("W/", "")
    return any(t.strip().replace("W/", "") == bare or t.strip() == "*" for t in header.split(","))


class ETagMiddleware(BaseHTTPMiddleware):
    """Adds ETag to the polled GET endpoints and answers 304 (no body) when nothing changed."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method != "GET" or response.status_code != 200 or not ETAG_PATHS.match(request.url.path):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = 'W/"%s"' % hashlib.sha1(body).hexdigest()[:24]
        cache = {"ETag": etag, "Cache-Control": "private, no-cache"}  # private: depends on who is asking; revalidate every time
        inm = request.headers.get("if-none-match")
        if inm and _matches(inm, etag):
            return Response(status_code=304, headers=cache)
        headers = dict(response.headers)
        headers.update(cache)
        return Response(content=body, status_code=200, headers=headers, media_type=response.media_type)
