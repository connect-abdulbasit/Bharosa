"""Mock government services. Every response includes "simulated": true.

Standalone: no imports from other folders. Shapes follow contracts/schemas.py.
"""
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import chaos

DATA = Path(__file__).parent / "data"
IDENTITY: Dict[str, Dict[str, Any]] = {p["cnic"]: p for p in json.loads((DATA / "identity.json").read_text())}
LEDGER: Dict[str, List[Dict[str, Any]]] = json.loads((DATA / "ledger.json").read_text())
SENDERS: Dict[str, List[str]] = json.loads((DATA / "senders.json").read_text())
COMPLAINTS: List[Dict[str, Any]] = []
NOTIFICATIONS: List[Dict[str, Any]] = []

app = FastAPI(title="Bharosa Mock Services (SIMULATED)", version="0.1.0",
              description="All data and responses are simulated. No real NADRA/Raast/SMS.")


class ChaosUpdate(BaseModel):
    timeout: Optional[bool] = None
    error_500: Optional[bool] = None
    missing_record: Optional[bool] = None
    duplicate_payment: Optional[bool] = None
    lookalike_sender: Optional[bool] = None
    slow_network_ms: Optional[int] = None


class ComplaintCreate(BaseModel):
    cnic: str
    category: str
    description: str


class NotifyRequest(BaseModel):
    to: str
    message: str
    channel: str = "sms"


def apply_chaos() -> None:
    """Dependency run by every data endpoint (not by /chaos or /health)."""
    state = chaos.get()
    delay = int(state["slow_network_ms"])
    if delay > 0:
        time.sleep(min(delay, 10000) / 1000.0)
    if state["timeout"]:
        raise HTTPException(status_code=504, detail={"error": "upstream_timeout", "simulated": True})
    if state["error_500"]:
        raise HTTPException(status_code=500, detail={"error": "internal_error", "simulated": True})


@app.exception_handler(HTTPException)
async def http_exc(_, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
    detail["simulated"] = True
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "simulated": True}


@app.get("/identity/{cnic}", dependencies=[Depends(apply_chaos)])
def identity(cnic: str) -> Dict[str, Any]:
    if chaos.get()["missing_record"] or cnic not in IDENTITY:
        raise HTTPException(status_code=404, detail={"error": "record_not_found"})
    return dict(IDENTITY[cnic], simulated=True)


@app.get("/ledger/{cnic}", dependencies=[Depends(apply_chaos)])
def ledger(cnic: str) -> Dict[str, Any]:
    if chaos.get()["missing_record"] or cnic not in LEDGER:
        raise HTTPException(status_code=404, detail={"error": "record_not_found"})
    payments = list(LEDGER[cnic])
    if chaos.get()["duplicate_payment"] and payments:
        dup = dict(payments[0])
        dup["payment_id"] = dup["payment_id"] + "-dup"
        payments.append(dup)
    return {"cnic": cnic, "payments": payments, "simulated": True}


@app.post("/complaints", dependencies=[Depends(apply_chaos)])
def complaints(body: ComplaintCreate) -> Dict[str, Any]:
    ticket_id = "TKT-%s" % uuid.uuid4().hex[:8].upper()
    COMPLAINTS.append(dict(body.model_dump(), ticket_id=ticket_id))
    return {"ticket_id": ticket_id, "simulated": True}


@app.get("/senders", dependencies=[Depends(apply_chaos)])
def senders() -> Dict[str, Any]:
    codes = list(SENDERS["official"])
    if chaos.get()["lookalike_sender"]:
        codes.extend(SENDERS["lookalikes"])  # simulates a polluted/spoofed registry
    return {"senders": codes, "simulated": True}


@app.post("/notify", dependencies=[Depends(apply_chaos)])
def notify(body: NotifyRequest) -> Dict[str, Any]:
    message_id = "MSG-%s" % uuid.uuid4().hex[:8].upper()
    NOTIFICATIONS.append(dict(body.model_dump(), message_id=message_id))
    return {"message_id": message_id, "simulated": True}


@app.get("/chaos")
def get_chaos() -> Dict[str, Any]:
    return dict(chaos.get(), simulated=True)


@app.post("/chaos")
def set_chaos(body: ChaosUpdate) -> Dict[str, Any]:
    return dict(chaos.update(body.model_dump()), simulated=True)


@app.post("/chaos/reset")
def reset_chaos() -> Dict[str, Any]:
    return dict(chaos.reset(), simulated=True)
