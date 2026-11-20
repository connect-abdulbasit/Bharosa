"""Audit log. EVERY state change (user, AI or agent) must call log().

Prototype: in-memory list. TODO(Basit): append-only audit_log table; no update/delete paths.
"""
import itertools
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

ENTRIES: List[Dict[str, Any]] = []
_counter = itertools.count(1)


def log(actor: str, action: str, before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]],
        target: str = "", actor_type: str = "user") -> Dict[str, Any]:
    entry = {
        "id": "aud-live-%04d" % next(_counter),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "actor_type": actor_type,
        "action": action,
        "target": target,
        "before": before,
        "after": after,
    }
    ENTRIES.append(entry)
    return entry
