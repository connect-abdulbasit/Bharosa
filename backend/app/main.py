"""Bharosa platform API. Run: uvicorn app.main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app import errors, logging_setup
from app.config import settings
from app.db import session_factory
from app.limiter import limiter
from app.middleware import ETagMiddleware, RequestContextMiddleware
from app.routers import (admin, apikeys, audit, auth, cases, claims, consent, documents, evalr, helper, messages, public, queue,
                         notifications, rules, scam_map)
from app.services import jobs
from app.services.mocks_client import mocks_status

log = logging.getLogger("bharosa")

DESCRIPTION = """
Trusted assistance layer for the **fictional Sahara Relief Programme**. **PROTOTYPE: not an official service; every identity,
payment and SMS service is simulated** (`"simulated": true`).

**Auth.** `POST /auth/login` returns a JWT (`Authorization: Bearer <token>`). Roles: citizen, helper, officer, admin, auditor,
enforced server-side. Partners can use an **`X-API-Key`** header on the read-only `/public` routes (use *Authorize* below).

**Safe by design.** Every state change is in the append-only audit log. Consent is checked before any mock call. Any payment
needs an officer and is made once (idempotency key). Mock failures send a case to a human with a note, never a raw 500.

**Weak internet.** Claims run in the background (`202` + `GET /claims/{id}/progress`). Polled GETs support `ETag` /
`If-None-Match` (`304`). Responses are gzip-compressed and omit empty fields.

**Limits.** `/auth/login` 5/min per IP (30/min while the demo mode is on); `/public` 30/min per API key; everything else 120/min per IP. Errors always look like
`{"error", "message", "request_id"}`.
"""

TAGS = [
    {"name": "auth", "description": "Login (JWT) and the current user. Citizens can set the PIN helpers need to grant consent for them."},
    {"name": "cases", "description": "Case management: create, list (row-level filtered), assign, escalate, officer decision, close."},
    {"name": "claims", "description": "The claim agent: file in the background (202), poll progress (ETag), resume after a failure."},
    {"name": "messages", "description": "Scam check for SMS text, including a look-alike sender check."},
    {"name": "documents", "description": "ID photo upload with OCR and blur check (asks for a retake when unclear)."},
    {"name": "rules", "description": "Versioned, validated decision rules (json-logic). A new version is active immediately."},
    {"name": "consent", "description": "See, grant, withdraw and correct consent. Helpers need the citizen's PIN to grant."},
    {"name": "audit", "description": "Read-only, append-only audit log of user, AI and agent actions."},
    {"name": "queue", "description": "Officer review queue sorted by risk, then confidence, then age."},
    {"name": "helper", "description": "Helper Mode: the citizens linked to this helper."},
    {"name": "apikeys", "description": "Admin: create (shown once), list and revoke partner API keys."},
    {"name": "public", "description": "Read-only partner API. Header `X-API-Key`. Rate limited per key."},
    {"name": "notifications", "description": "In-app messages (Urdu + English) the notifications service creates when a case status changes; consent-gated."},
    {"name": "eval", "description": "Evaluation numbers computed from real decisions and checks."},
    {"name": "scam-map", "description": "Privacy-safe scam counts by area, day and reason (areas under 3 reports grouped as 'other')."},
    {"name": "admin", "description": "Demo controls (DEMO_MODE=1): one-click reset to a known state, outage switches for the fake mocks."},
    {"name": "meta", "description": "Health."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_setup.setup()
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, release=settings.APP_VERSION,
                            send_default_pii=False, traces_sample_rate=0.0)
            log.info("sentry enabled")
        except ImportError:
            log.warning("SENTRY_DSN is set but sentry-sdk is not installed (pip install 'bharosa-backend[monitoring]')")
        except Exception as exc:  # monitoring must never stop the API from starting (e.g. a malformed DSN)
            log.warning("sentry could not be initialised (%s): continuing without it", exc)
    import bharosa_ai

    caps = bharosa_ai.capabilities()
    fallbacks = [n for n, f in caps["functions"].items() if f["mode"] not in ("real", "stub")]
    # ONE clear line: which AI functions are real, which fall back to an offline helper, and why. Adding a key + restart changes it.
    (log.warning if fallbacks else log.info)("AI startup: %s", bharosa_ai.describe())
    if settings.PIPELINE_MODE == "thread":
        jobs.worker.start()
    yield
    jobs.worker.stop()


app = FastAPI(title="Bharosa Platform API (PROTOTYPE - simulated data)", version=settings.APP_VERSION, description=DESCRIPTION,
              openapi_tags=TAGS, lifespan=lifespan)
app.state.limiter = limiter
errors.install(app)

# add_middleware: the LAST one added is the OUTERMOST. Order outer -> inner: CORS, request context, gzip, rate limit, etag.
app.add_middleware(ETagMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"],
                   allow_headers=["*"], expose_headers=["X-Request-ID", "ETag"])

for module in (admin, auth, cases, claims, messages, documents, rules, consent, audit, queue, helper, apikeys, public, evalr, scam_map, notifications):
    app.include_router(module.router)


def _ai_modes() -> Dict[str, str]:
    import bharosa_ai

    return {n: f["mode"] for n, f in bharosa_ai.capabilities()["functions"].items()}


@app.get("/health", tags=["meta"], summary="Liveness + dependencies")
@limiter.exempt
def health(response: Response) -> Dict[str, Any]:
    """200 when the database answers (what a deploy platform needs). Reports mocks reachability and the worker, but a mocks
    outage only shows as `degraded`: the app still works (cases go to a human)."""
    db_ok = True
    try:
        with session_factory()() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        log.exception("health: database check failed")
        db_ok = False
    mocks = mocks_status()
    if not db_ok:
        response.status_code = 503
    return {"status": "ok" if db_ok and mocks["reachable"] else ("degraded" if db_ok else "down"),
            "database": "ok" if db_ok else "down", "mocks": mocks, "ai_mode": settings.AI_MODE, "ai_functions": _ai_modes(),
            "worker": {"mode": settings.PIPELINE_MODE, "alive": jobs.worker.alive() if settings.PIPELINE_MODE == "thread" else None},
            "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT, "simulated": True}
