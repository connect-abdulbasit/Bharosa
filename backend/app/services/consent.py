"""Consent. consent.require() MUST run before any identity/payment/complaint/notification mock call.

Every change and every blocked attempt writes a consent_event AND an audit entry.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Consent, ConsentEvent, User
from app.services import audit
from contracts.enums import ConsentScope

DEFAULT_RECIPIENT = {
    "identity": "Identity service (simulated NADRA)",
    "payments": "Payment ledger (simulated Raast)",
    "complaints": "Complaints desk (simulated)",
    "notifications": "SMS notifications (simulated)",
}
PURPOSE = {
    "identity": "Check your name and ID number against the programme list",
    "payments": "Check which payments you received",
    "complaints": "File a complaint on your behalf",
    "notifications": "Send you updates about your case",
}


class ConsentRequired(Exception):
    def __init__(self, citizen_id: str, scope: str):
        super().__init__("Consent for '%s' is required (withdrawn or never granted)" % scope)
        self.citizen_id = citizen_id
        self.scope = scope


def _scope(scope) -> str:
    return scope.value if isinstance(scope, ConsentScope) else str(scope)


def get_consent(db: Session, citizen_id: str, scope) -> Optional[Consent]:
    return db.execute(select(Consent).where(Consent.citizen_id == citizen_id, Consent.scope == _scope(scope))).scalar_one_or_none()


def record_event(db: Session, consent: Consent, action: str, actor_id: Optional[str], reason: Optional[str] = None) -> None:
    db.add(ConsentEvent(consent_id=consent.id, action=action, actor_id=actor_id, reason=reason))


def require(db: Session, citizen_id: str, scope, actor: Optional[User] = None, purpose: Optional[str] = None) -> Consent:
    """Return the granted consent or raise ConsentRequired (after logging + committing the blocked attempt)."""
    sc = _scope(scope)
    consent = get_consent(db, citizen_id, sc)
    if consent is not None and consent.status == "granted":
        return consent
    if consent is None:  # never asked: record a pending row so the attempt has something to attach to
        consent = Consent(citizen_id=citizen_id, scope=sc, granted_to=DEFAULT_RECIPIENT.get(sc), status="pending")
        db.add(consent)
        db.flush()
    actor_id = actor.id if actor is not None else None
    record_event(db, consent, "blocked", actor_id, purpose or "access attempted without consent")
    audit.log(db, "user" if actor is not None else "system", actor_id, "consent.blocked", "consent", consent.id,
              before={"status": consent.status},
              after={"citizen_id": citizen_id, "scope": sc, "purpose": purpose})
    db.commit()  # keep the evidence even though the request is about to fail
    raise ConsentRequired(citizen_id, sc)
