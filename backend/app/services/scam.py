"""Scam check: ai.classify_message + sender check against the (mock) official sender list.

Safety rules (never over-claim):
- a message from a sender NOT on the official list can never be 'genuine' (downgraded to 'unsure');
- a sender that looks like an official code (9O9O vs 9090) is a strong scam signal;
- if the sender list cannot be fetched we say so and never claim the sender is official.
"""
import hashlib
import re
from typing import Any, Dict, List, Optional

import bharosa_ai as ai
from sqlalchemy.orm import Session

from app.models import CheckedMessage
from app.services.mock_errors import MockUnavailable

OFFICIAL_FALLBACK = ["9090"]
EXPLAIN = {
    "scam": ("This message looks fake. The official code is 9090. Do not open any link or send any money.",
             "یہ پیغام جعلی لگتا ہے۔ سرکاری کوڈ 9090 ہے۔ کوئی لنک نہ کھولیں اور کسی کو پیسے نہ بھیجیں۔"),
    "genuine": ("This message came from an official code and looks fine. If anyone asks you for money, say no.",
                "یہ پیغام سرکاری کوڈ سے آیا ہے اور ٹھیک لگتا ہے۔ اگر کوئی پیسے مانگے تو انکار کریں۔"),
    "unsure": ("We are not sure about this message. Do not act on it. Ask your helper or an officer.",
               "ہمیں اس پیغام کا یقین نہیں۔ اس پر عمل نہ کریں۔ اپنے مددگار یا افسر سے پوچھیں۔"),
}


def _skeleton(code: str) -> str:
    """Fold look-alike characters so '9O9O' and '9090' compare equal."""
    s = code.strip().lower()
    return re.sub(r"[^a-z0-9]", "", s.translate(str.maketrans({"o": "0", "l": "1", "i": "1", "|": "1", "s": "5", "b": "8"})))


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()


def check_message(db: Session, mocks: Any, text: str, sender: str, area: Optional[str] = None) -> Dict[str, Any]:
    verdict = ai.classify_message(text, sender)
    label, confidence = verdict.label.value, float(verdict.confidence)
    reasons: List[str] = list(verdict.reasons)

    official: Optional[List[str]] = None
    try:
        official = list(mocks.senders()["senders"])
    except (MockUnavailable, KeyError, TypeError):
        reasons.append("We could not check the official sender list right now, so we cannot confirm this sender.")
    is_official = bool(official) and sender.strip() in official
    if official is not None and not is_official:
        look = next((o for o in official if _skeleton(o) == _skeleton(sender) and o != sender.strip()), None)
        if look:
            reasons.append("Sender '%s' looks like the official code '%s' but is not it (look-alike)." % (sender, look))
            if label != "scam":
                label, confidence = "scam", max(confidence, 0.9)
        elif label == "genuine":
            reasons.append("The sender is not on the official list, so we cannot call this genuine.")
            label, confidence = "unsure", min(confidence, 0.6)
    if official is None and label == "genuine":
        label, confidence = "unsure", min(confidence, 0.6)

    en, ur = EXPLAIN[label]
    db.add(CheckedMessage(text_hash=text_hash(text), label=label, confidence=round(confidence, 2), reasons=reasons,
                          sender=sender.strip()[:60], area=area))
    return {"label": label, "confidence": round(confidence, 2), "reasons": reasons, "official_sender": is_official,
            "explanation_ur": ur, "explanation_en": en, "model_version": verdict.model_version}
