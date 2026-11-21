"""Services app (notifications + webhooks + job log). Run: PYTHONPATH=. uvicorn services.main:app --port 8002
All endpoints except /health need X-Service-Key (SERVICES_API_KEY)."""
import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services import common
from services.notifications import service as notif
from services.webhooks import service as hooks

app = FastAPI(title="Bharosa Services (SIMULATED)", version="0.1.0")


def service_key(x_service_key: Optional[str] = Header(default=None)) -> None:
    expected = os.environ.get("SERVICES_API_KEY", "dev-services-key-not-for-production")
    if not secrets.compare_digest(x_service_key or "", expected):
        raise HTTPException(status_code=401, detail="service key required")


auth = [Depends(service_key)]


class Consent(BaseModel):
    cnic: str = Field(..., pattern=r"^\d{13}$")
    granted: bool


class Send(BaseModel):
    cnic: str = Field(..., pattern=r"^\d{13}$")
    to: str = Field(..., max_length=40)
    key: str
    lang: str = "ur"


class Sub(BaseModel):
    url: str
    events: List[str]


class Event(BaseModel):
    event: str
    payload: Dict[str, Any] = {}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "simulated": True}


@app.post("/notifications/consent", dependencies=auth)
def set_consent(b: Consent) -> Dict[str, Any]:
    notif.set_consent(b.cnic, b.granted)
    return {"cnic": b.cnic, "granted": b.granted, "simulated": True}


@app.post("/notifications/send", dependencies=auth)
def send(b: Send) -> Dict[str, Any]:
    return notif.send(b.cnic, b.to, b.key, b.lang)


@app.get("/notifications", dependencies=auth)
def inbox(cnic: Optional[str] = None) -> Dict[str, Any]:
    return {"items": [n for n in notif.LOG if cnic in (None, n["cnic"])], "simulated": True}


@app.post("/webhooks/subscriptions", status_code=201, dependencies=auth)
def subscribe(b: Sub) -> Dict[str, Any]:
    try:
        return hooks.subscribe(b.url, b.events)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/webhooks/subscriptions", dependencies=auth)
def subs() -> Dict[str, Any]:
    return {"items": [{k: v for k, v in s.items() if k != "secret"} for s in hooks.SUBS.values()]}


@app.delete("/webhooks/subscriptions/{sub_id}", dependencies=auth)
def unsubscribe(sub_id: str) -> Dict[str, Any]:
    if hooks.SUBS.pop(sub_id, None) is None:
        raise HTTPException(status_code=404, detail="not found")
    common.audit("webhook.unsubscribed", id=sub_id)
    return {"deleted": sub_id}


@app.post("/events", status_code=202, dependencies=auth)
def event(b: Event, bg: BackgroundTasks) -> Dict[str, Any]:
    """Target for backend events.emit(): fan out to subscribers in the background (retries must not block the caller)."""
    if b.event not in hooks.EVENTS:
        raise HTTPException(status_code=422, detail="unknown event")
    bg.add_task(hooks.dispatch, b.event, b.payload)
    return {"accepted": True, "simulated": True}


@app.get("/webhooks/deliveries", dependencies=auth)
def deliveries() -> Dict[str, Any]:
    return {"items": hooks.LOG}


@app.get("/jobs", dependencies=auth)
def jobs() -> Dict[str, Any]:
    return {"items": list(common.JOBS), "audit": list(common.AUDIT)[-50:]}
