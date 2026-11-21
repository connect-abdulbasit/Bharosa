"""Optional calls to the services app (/services): in-app notifications and signed webhooks. NEVER blocks or breaks the user.

- Off unless NOTIFICATIONS_URL / WEBHOOKS_URL is set (empty = nothing happens).
- Runs in a small background pool (PIPELINE_MODE=inline, used by tests, runs it in the caller so a test can look at the result).
- Every failure is caught and logged: a dead or slow service must never change what the citizen sees.
- Notifications are consent-gated TWICE: here (the platform's own `notifications` consent) and again inside the service (default deny).
- Webhooks: the services app signs every delivery to its subscribers (HMAC-SHA256, timestamped, retried 1/5/30 s, dead-lettered).
  The event payload only carries ids and statuses (no names, no CNIC).
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.services import consent as consent_service

log = logging.getLogger("bharosa.outbound")
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="outbound")
# case status -> template key of the notifications service (services/notifications/service.py)
TEMPLATE_FOR_STATUS = {"approved": "case_approved", "needs_more_proof": "needs_more_proof", "with_officer": "with_officer",
                       "rejected": "case_rejected", "closed": "case_closed"}


def _headers() -> Dict[str, str]:
    return {"X-Service-Key": settings.SERVICES_API_KEY}


def _run(fn, *args) -> None:
    if settings.PIPELINE_MODE == "inline":
        fn(*args)
    else:
        _POOL.submit(fn, *args)


def _post(url: str, json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        r = httpx.post(url, json=json, headers=_headers(), timeout=settings.SERVICES_TIMEOUT_SECONDS)
        r.raise_for_status()
        return r.json()
    except Exception as exc:  # any failure: log and carry on
        log.warning("services call failed (%s): %s", url, str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
        return None


def _notify(cnic: str, phone: str, key: str) -> None:
    base = settings.NOTIFICATIONS_URL
    if _post(base + "/notifications/consent", {"cnic": cnic, "granted": True}) is None:  # the service fails closed without this
        return
    _post(base + "/notifications/send", {"cnic": cnic, "to": phone or "0000000000", "key": key, "lang": "both"})


def notify_status_change(db: Session, citizen_id: str, to_status: str, case_id: str) -> Optional[str]:
    """Queue an in-app Urdu + English message for a status change when NOTIFICATIONS_URL is set and the citizen's `notifications`
    consent is granted. Returns what happened ("queued", "no_consent", ...) for logs and tests; never raises."""
    try:
        if not settings.NOTIFICATIONS_URL:
            return None
        key = TEMPLATE_FOR_STATUS.get(to_status)
        if key is None:
            return "no_template"
        citizen = db.get(User, citizen_id)
        if citizen is None or not citizen.cnic or len(citizen.cnic) != 13:
            return "no_cnic"
        c = consent_service.get_consent(db, citizen_id, "notifications")
        if c is None or c.status != "granted":
            return "no_consent"  # no consent -> no message, no call
        _run(_notify, citizen.cnic, citizen.phone or "", key)
        return "queued"
    except Exception:
        log.exception("notification for case %s could not be queued", case_id)
        return "error"


def forward_event(name: str, payload: Dict[str, Any]) -> bool:
    """Hand an event to the webhooks service (it signs, retries and logs deliveries). True when it was handed over or queued."""
    try:
        if not settings.WEBHOOKS_URL:
            return False
        _run(_post, settings.WEBHOOKS_URL + "/events", {"event": name, "payload": payload})
        return True
    except Exception:
        log.exception("event %s could not be forwarded", name)
        return False


def inbox(citizen: User) -> list:
    """The citizen's own in-app messages from the notifications service (newest first). [] when off or unreachable."""
    if not settings.NOTIFICATIONS_URL or not citizen.cnic:
        return []
    try:
        r = httpx.get(settings.NOTIFICATIONS_URL + "/notifications", params={"cnic": citizen.cnic}, headers=_headers(),
                      timeout=settings.SERVICES_TIMEOUT_SECONDS)
        r.raise_for_status()
        items = [n for n in r.json().get("items", []) if n.get("status") == "sent"]
        return [{"id": n["id"], "key": n["key"], "text_ur": n.get("text_ur"), "text_en": n.get("text_en"), "at": n.get("at"),
                 "simulated": True} for n in reversed(items)][:20]
    except Exception as exc:
        log.warning("inbox unavailable: %s", str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
        return []
