"""Shared enums. Keep in sync with enums.ts (additive changes only)."""
from enum import Enum


class Role(str, Enum):
    citizen = "citizen"
    helper = "helper"
    officer = "officer"
    admin = "admin"
    auditor = "auditor"


class CaseStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    needs_more_proof = "needs_more_proof"
    with_officer = "with_officer"
    approved = "approved"
    rejected = "rejected"
    closed = "closed"


class DecisionAction(str, Enum):
    auto_handle = "auto_handle"
    ask_more = "ask_more"
    send_to_human = "send_to_human"


class MessageLabel(str, Enum):
    scam = "scam"
    genuine = "genuine"
    unsure = "unsure"


class ConsentScope(str, Enum):
    identity = "identity"
    payments = "payments"
    complaints = "complaints"
    notifications = "notifications"
