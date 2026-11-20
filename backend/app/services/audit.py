"""Audit log. EVERY create/update/delete, login and blocked access calls log().

log() only adds the row to the caller's session, so the audit entry commits atomically with the change.
For failures that roll back (login failure, blocked consent) the caller commits first, then raises.
The table is append-only (ORM guards in models/audit.py; no update/delete routes exist).
"""
from contextvars import ContextVar
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

ACTOR_TYPES = ("user", "ai", "agent", "system")


def log(db: Session, actor_type: str, actor_id: Optional[str], action: str, entity: str,
        entity_id: Optional[str] = None, before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None) -> AuditLog:
    if actor_type not in ACTOR_TYPES:
        raise ValueError("actor_type must be one of %s" % (ACTOR_TYPES,))
    row = AuditLog(actor_type=actor_type, actor_id=actor_id, action=action, entity=entity, entity_id=entity_id,
                   before=before, after=after, request_id=request_id_var.get())
    db.add(row)
    return row
