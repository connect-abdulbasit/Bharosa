from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class Consent(Base):
    __tablename__ = "consents"
    __table_args__ = (UniqueConstraint("citizen_id", "scope", name="uq_consent_citizen_scope"),)

    id: Mapped[str] = mapped_column(String(60), primary_key=True, default=new_id)
    citizen_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    scope: Mapped[str] = mapped_column(String(20))  # identity | payments | complaints | notifications
    granted_to: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(15), default="granted")  # granted | withdrawn | pending
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ConsentEvent(Base):
    __tablename__ = "consent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    consent_id: Mapped[str] = mapped_column(ForeignKey("consents.id"), index=True)
    action: Mapped[str] = mapped_column(String(15))  # grant | withdraw | correct | blocked
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # citizen who confirmed (PIN) a helper action
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
