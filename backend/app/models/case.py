from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, new_id, utcnow


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    citizen_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    notes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)  # [{author, text, created_at}]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(20))  # missing | short_paid
    expected_amount: Mapped[int] = mapped_column(Integer, default=0)
    received_amount: Mapped[int] = mapped_column(Integer, default=0)
    month: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # YYYY-MM
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[Optional[str]] = mapped_column(ForeignKey("cases.id"), index=True, nullable=True)  # set when attached to a claim
    owner_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)  # the citizen the document is about
    kind: Mapped[str] = mapped_column(String(30))
    file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ocr_fields: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    blur_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    format_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    action: Mapped[str] = mapped_column(String(30))  # AI: DecisionAction; officer: approve|reject|request_more
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[List[str]] = mapped_column(JSON, default=list)
    trace: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    rule_id: Mapped[Optional[str]] = mapped_column(ForeignKey("rules.id"), nullable=True)
    rule_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(36))  # 'ai' or a user id
    payment_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # pending | paid | failed
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)  # case_id:decision_id
    payment_ref: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)  # reference returned by the payments rail
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CheckedMessage(Base):
    """Every scam check, for the evaluation page and a future Scam Map. Stores a hash, never the text."""

    __tablename__ = "checked_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    text_hash: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(10))
    confidence: Mapped[float] = mapped_column(Float)
    reasons: Mapped[List[str]] = mapped_column(JSON, default=list)
    sender: Mapped[str] = mapped_column(String(60))
    area: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    """Background work queue (database-backed, so queued claims survive a restart)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(30))  # claim_start | claim_resume
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(36))  # who asked (audit + consent actor)
    status: Mapped[str] = mapped_column(String(10), index=True, default="queued")  # queued | running | done | failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
