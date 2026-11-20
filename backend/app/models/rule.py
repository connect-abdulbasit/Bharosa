from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    active_version: Mapped[int] = mapped_column(Integer, default=1)


class RuleVersion(Base):
    """Immutable: new versions are inserted, existing ones are never edited."""

    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_rule_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    logic: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # json-logic
    thresholds: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
