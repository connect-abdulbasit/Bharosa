"""Case lifecycle rules. Every status change goes through change_status() so it is always audited."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Case, User
from app.services import audit, events
from app.services.serialize import case_snapshot, iso
from app.models.base import utcnow

ALLOWED = {
    "draft": {"submitted", "closed"},
    "submitted": {"with_officer", "needs_more_proof", "approved", "rejected", "closed"},
    "needs_more_proof": {"needs_more_proof", "submitted", "with_officer", "approved", "rejected", "closed"},
    "with_officer": {"approved", "rejected", "needs_more_proof", "closed"},
    "approved": {"closed"},
    "rejected": {"closed"},
    "closed": set(),
}


def can_move(case: Case, new_status: str) -> bool:
    return new_status in ALLOWED.get(case.status, set())


def add_note(case: Case, author: str, text: str) -> None:
    case.notes = list(case.notes or []) + [{"author": author, "text": text, "created_at": iso(utcnow())}]


def change_status(db: Session, case: Case, new_status: str, actor: User, action: str, note: Optional[str] = None,
                  step: Optional[str] = None) -> None:
    if not can_move(case, new_status):
        raise HTTPException(status_code=409, detail="Cannot move a case from '%s' to '%s'" % (case.status, new_status))
    before = case_snapshot(case)
    case.status = new_status
    case.current_step = step or new_status
    if note:
        add_note(case, actor.id, note)
    db.flush()
    audit.log(db, "user", actor.id, action, "case", case.id, before=before, after=case_snapshot(case))
    events.emit("case.status_changed", {"case_id": case.id, "citizen_id": case.citizen_id, "from": before["status"], "to": new_status,
                "by": actor.id, "action": action, "at": iso(utcnow())}, db)
