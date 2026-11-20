from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # login id (extra to spec)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    cnic: Mapped[Optional[str]] = mapped_column(String(13), unique=True, nullable=True)  # FAKE, starts 00000
    role: Mapped[str] = mapped_column(String(20), index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    pin_hash: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # 4-digit PIN (citizens), bcrypt
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Family(Base):
    """Links a helper to a citizen they may act for (Helper Mode)."""

    __tablename__ = "families"
    __table_args__ = (UniqueConstraint("helper_id", "citizen_id", name="uq_family_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    helper_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    citizen_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
