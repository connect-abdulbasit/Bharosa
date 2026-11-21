"""One error format for everything: {"error": <code>, "message": <human text>, "request_id": <id>}.
422 adds "fields": [{"field", "in", "message"}]. Stack traces are logged (with the request id), never returned."""
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.consent import ConsentRequired

log = logging.getLogger("bharosa.error")

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed", 409: "conflict",
         413: "payload_too_large", 415: "unsupported_media_type", 422: "validation_error", 429: "rate_limited",
         503: "service_unavailable"}


def request_id_of(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


def error_body(request: Request, error: str, message: str, **extra: Any) -> Dict[str, Any]:
    return dict({"error": error, "message": message, "request_id": request_id_of(request)}, **extra)


def respond(request: Request, status: int, error: str, message: str, headers: Optional[Dict[str, str]] = None, **extra: Any) -> JSONResponse:
    h = dict(headers or {})
    if request_id_of(request):
        h["X-Request-ID"] = str(request_id_of(request))
    return JSONResponse(status_code=status, content=error_body(request, error, message, **extra), headers=h)


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return respond(request, exc.status_code, CODES.get(exc.status_code, "error"), message, getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = []
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", ())]
            fields.append({"in": loc[0] if loc else "body", "field": ".".join(loc[1:]) or (loc[0] if loc else ""), "message": e.get("msg", "invalid")})
        names = ", ".join(sorted({f["field"] for f in fields if f["field"]})) or "request"
        return respond(request, 422, "validation_error", "Please check these fields: %s" % names, fields=fields)  # inputs are never echoed

    @app.exception_handler(ConsentRequired)
    async def consent_required(request: Request, exc: ConsentRequired):
        return respond(request, 403, "consent_required",
                       "This needs the citizen's consent for '%s'. It is withdrawn or was never given." % exc.scope,
                       scope=exc.scope, citizen_id=exc.citizen_id)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(request: Request, exc: RateLimitExceeded):
        return respond(request, 429, "rate_limited", "Too many requests (limit: %s). Please wait a minute and try again." % exc.detail,
                       headers={"Retry-After": "60"})

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("unhandled error on %s %s", request.method, request.url.path, exc_info=exc, extra={"request_id": request_id_of(request)})
        return respond(request, 500, "internal_error", "Something went wrong on our side. Please try again; if it keeps happening, tell the help desk this request id.")
