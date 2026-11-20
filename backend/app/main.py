"""Bharosa platform API. Run: uvicorn app.main:app --reload --port 8000"""
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import apikeys, audit, auth, cases, claims, consent, documents, evalr, helper, messages, queue, rules

app = FastAPI(
    title="Bharosa Platform API (PROTOTYPE - simulated data)",
    version="0.1.0",
    description="Trusted assistance layer for the fictional Sahara Relief Programme. "
                "Not an official service. All identity, payment and SMS services are simulated.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for module in (auth, cases, claims, messages, documents, rules, consent, audit, queue, helper, apikeys, evalr):
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health() -> Dict[str, object]:
    return {"status": "ok", "ai_mode": settings.AI_MODE, "mocks": settings.MOCKS_URL or "fake", "simulated": True}
