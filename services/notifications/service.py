"""Consent-aware notifications: consent (default deny) -> Urdu/English template -> mock POST /notify, with retry."""
import os
import uuid
from typing import Any, Dict, List

import httpx

from services.common import audit, retry

TEMPLATES = {
    "case_approved": {"ur": "آپ کا کیس منظور ہو گیا ہے۔ رقم جلد ملے گی۔", "en": "Your case is approved. The payment will follow."},
    "needs_more_proof": {"ur": "براہ کرم شناختی کارڈ کی صاف تصویر دوبارہ بھیجیں۔", "en": "Please send a clear photo of your ID card again."},
    "with_officer": {"ur": "آپ کا کیس افسر کو بھیج دیا گیا ہے۔", "en": "Your case was sent to an officer."},
    "scam_warning": {"ur": "یہ پیغام جعلی ہو سکتا ہے۔ کوئی رقم یا کوڈ نہ دیں۔", "en": "This message may be fake. Do not pay or share any code."},
}
CONSENT: Dict[str, bool] = {}   # cnic -> notifications consent; a missing entry means NO (fail closed)
LOG: List[Dict[str, Any]] = []  # in-app inbox + mock SMS log (newest last)


def set_consent(cnic: str, granted: bool) -> None:
    CONSENT[cnic] = granted
    audit("notifications.consent", cnic=cnic, granted=granted)


def _post(to: str, text: str) -> str:
    r = httpx.post(os.environ.get("MOCKS_URL", "http://localhost:8001").rstrip("/") + "/notify",
                   json={"to": to, "message": text, "channel": "sms"}, timeout=5)
    r.raise_for_status()
    return r.json()["message_id"]


def send(cnic: str, to: str, key: str, lang: str = "ur") -> Dict[str, Any]:
    """Consent is checked HERE, before anything leaves. Blocked and failed sends are logged, never raised."""
    entry = {"id": "N-" + uuid.uuid4().hex[:8], "cnic": cnic, "key": key, "lang": lang, "simulated": True}
    if not CONSENT.get(cnic, False):
        entry["status"] = "blocked"
        audit("notification.blocked", cnic=cnic, key=key, reason="no notifications consent")
    elif key not in TEMPLATES or lang not in ("ur", "en"):
        entry["status"] = "rejected"
    else:
        entry["text"] = TEMPLATES[key][lang]
        job = retry("notify:" + entry["id"], lambda: _post(to, entry["text"]))
        entry.update(status="sent" if job["status"] == "done" else "failed", message_id=job.get("result"), attempts=job["attempts"])
        audit("notification." + entry["status"], cnic=cnic, key=key, id=entry["id"])
    LOG.append(entry)
    return entry
