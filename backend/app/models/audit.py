from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class AuditImmutable(Exception):
    """The audit log is append-only."""


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(10))  # user | ai | agent | system
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    before: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    after: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@event.listens_for(AuditLog, "before_update")
def _no_update(*_args: Any) -> None:
    raise AuditImmutable("audit_log rows cannot be updated")


@event.listens_for(AuditLog, "before_delete")
def _no_delete(*_args: Any) -> None:
    raise AuditImmutable("audit_log rows cannot be deleted")
