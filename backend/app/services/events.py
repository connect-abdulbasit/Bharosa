"""Hook point for outgoing events (webhooks). emit() is called when something worth telling partners happens.

It (1) writes an audit entry, (2) keeps the last events in a local list, (3) forwards the event to the webhooks service when
WEBHOOKS_URL is set (it signs and retries deliveries; a failure is logged and never blocks the caller) and (4) for a case status
change asks the notifications service for an in-app message (only with the citizen's `notifications` consent).
"""
from collections import deque
from typing import Any, Deque, Dict, Optional

from sqlalchemy.orm import Session

from app.services import audit, outbound

EMITTED: Deque[Dict[str, Any]] = deque(maxlen=1000)


def emit(name: str, payload: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    event = {"event": name, "payload": payload}
    EMITTED.append(event)
    if db is not None:
        audit.log(db, "system", "events", "event.%s" % name, "event", str(payload.get("case_id") or ""), after=event)
    outbound.forward_event(name, payload)
    if name == "case.status_changed" and db is not None:
        outbound.notify_status_change(db, str(payload.get("citizen_id") or ""), str(payload.get("to") or ""), str(payload.get("case_id") or ""))
    return event
