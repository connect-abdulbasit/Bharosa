"""Hook point for outgoing events (webhooks). emit() is called when something worth telling partners happens.

For now it (1) writes an audit entry and (2) keeps the last events in a local list.
TODO(Hadi): real webhook delivery (HMAC-signed POSTs to subscribers, retries with backoff, delivery log) -
replace the body of emit() or have it enqueue into services/webhooks. Keep the call sites unchanged.
"""
from collections import deque
from typing import Any, Deque, Dict, Optional

from sqlalchemy.orm import Session

from app.services import audit

EMITTED: Deque[Dict[str, Any]] = deque(maxlen=1000)


def emit(name: str, payload: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    event = {"event": name, "payload": payload}
    EMITTED.append(event)
    if db is not None:
        audit.log(db, "system", "events", "event.%s" % name, "event", str(payload.get("case_id") or ""), after=event)
    return event
