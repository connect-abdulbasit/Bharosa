"""Scam Map aggregation. Counts only, and small groups are folded into 'other' (k-anonymity, k=3):
no message text, no sender, no user id ever leaves this module."""
import re
from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CheckedMessage
from app.models.base import utcnow
from app.services.serialize import iso

MIN_GROUP = 3
CUE = re.compile(r"suspicious cue '([a-z0-9 .\-]{1,20})'", re.I)


def normalise_reason(reason: str) -> str:
    """Map a free-text reason to a fixed category: sender numbers / names inside the text must not leak."""
    low = reason.lower()
    if "look-alike" in low:
        return "Sender looks like the official code (look-alike)"
    if "not the official code" in low:
        return "Sender is not the official code"
    if "not on the official list" in low:
        return "Sender is not on the official list"
    if "official sender list" in low:
        return "Sender could not be verified"
    m = CUE.search(reason)
    if m:
        return "Suspicious wording: %s" % m.group(1).lower()
    return "Other"


def _fold(counter: Counter, other: str = "other") -> List[Dict[str, Any]]:
    out, folded = [], 0
    for key, n in counter.most_common():
        if n < MIN_GROUP or key == other:
            folded += n
        else:
            out.append((key, n))
    if folded:
        out.append((other, folded))
    return out


def build(db: Session, days: int) -> Dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = db.execute(select(CheckedMessage).where(CheckedMessage.label == "scam", CheckedMessage.created_at >= since)).scalars().all()
    areas: Counter = Counter((r.area or "unknown") for r in rows)
    reasons: Counter = Counter()
    per_day: Counter = Counter()
    for r in rows:
        for cat in {normalise_reason(x) for x in (r.reasons or [])}:
            reasons[cat] += 1
        per_day[r.created_at.strftime("%Y-%m-%d")] += 1
    today = utcnow().date()
    by_day = [{"day": (today - timedelta(days=d)).isoformat(), "count": per_day.get((today - timedelta(days=d)).isoformat(), 0)}
              for d in range(days - 1, -1, -1)]
    return {"generated_at": iso(utcnow()), "window_days": days, "min_group_size": MIN_GROUP, "total": len(rows),
            "by_area": [{"area": k, "count": n} for k, n in _fold(areas)], "by_day": by_day,
            "by_reason": [{"reason": k, "count": n} for k, n in _fold(reasons)]}
