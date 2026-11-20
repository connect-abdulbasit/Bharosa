"""Bharosa platform API. Run: uvicorn app.main:app --reload --port 8000"""
import logging
import uuid
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import apikeys, audit, auth, cases, claims, consent, documents, evalr, helper, messages, queue, rules
from app.services import audit as audit_service
from app.services.consent import ConsentRequired

log = logging.getLogger("bharosa")

app = FastAPI(
    title="Bharosa Platform API (PROTOTYPE - simulated data)",
    version="0.2.0",
    description="Trusted assistance layer for the fictional Sahara Relief Programme. "
                "Not an official service. All identity, payment and SMS services are simulated.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*", "X-Request-ID"], expose_headers=["X-Request-ID"])


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Tag every request so related audit entries can be grouped (X-Request-ID in and out)."""
    rid = (request.headers.get("x-request-id") or uuid.uuid4().hex)[:64]
    token = audit_service.request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        audit_service.request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(ConsentRequired)
async def consent_required_handler(request: Request, exc: ConsentRequired):
    return JSONResponse(status_code=403, content={
        "error": "consent_required", "scope": exc.scope, "citizen_id": exc.citizen_id,
        "detail": "This needs the citizen's consent for '%s'. It is withdrawn or was never given." % exc.scope})


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # Never leak stack traces to clients.
    log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": audit_service.request_id_var.get()})


for module in (auth, cases, claims, messages, documents, rules, consent, audit, queue, helper, apikeys, evalr):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> Dict[str, object]:
    return {"status": "ok", "ai_mode": settings.AI_MODE, "mocks": settings.MOCKS_URL or "fake", "simulated": True}
