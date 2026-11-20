"""Pydantic request/response models for the platform API (/backend) and mock services (/mocks).

Rules: additive changes only. Python 3.9 compatible (use Optional/List, not X | None).
Every mock response carries `simulated: true`.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from contracts.enums import CaseStatus, ConsentScope, DecisionAction, MessageLabel, Role


class SimulatedModel(BaseModel):
    """Base for anything coming from a mocked service."""

    simulated: bool = True


# --------------------------------------------------------------------------- shared shapes
class PersonRecord(SimulatedModel):
    cnic: str = Field(..., description="13-digit FAKE CNIC, always starts with 00000")
    full_name: str
    father_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    district: Optional[str] = None
    aliases: List[str] = Field(default_factory=list, description="Known spelling variants")
    phone_last4: Optional[str] = None


class Payment(BaseModel):
    payment_id: str
    amount_pkr: int
    date: str
    agent_id: str
    programme: str = "Sahara Relief Programme"


class RuleVersion(BaseModel):
    rule_id: str
    version: int
    name: str = "Sahara stipend decision rule"
    auto_handle_min: float = 0.90
    ask_more_min: float = 0.60
    red_flags: List[str] = Field(default_factory=list)
    logic: Dict[str, Any] = Field(default_factory=dict, description="json-logic expression")
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    note: Optional[str] = None


# --------------------------------------------------------------------------- mock services
class LedgerResponse(SimulatedModel):
    cnic: str
    payments: List[Payment]


class ComplaintCreate(BaseModel):
    cnic: str
    category: str
    description: str


class ComplaintResponse(SimulatedModel):
    ticket_id: str


class SendersResponse(SimulatedModel):
    senders: List[str]


class NotifyRequest(BaseModel):
    to: str
    message: str
    channel: str = "sms"


class NotifyResponse(SimulatedModel):
    message_id: str


class ChaosState(SimulatedModel):
    timeout: bool = False
    error_500: bool = False
    missing_record: bool = False
    duplicate_payment: bool = False
    lookalike_sender: bool = False
    slow_network_ms: int = 0


class ChaosUpdate(BaseModel):
    timeout: Optional[bool] = None
    error_500: Optional[bool] = None
    missing_record: Optional[bool] = None
    duplicate_payment: Optional[bool] = None
    lookalike_sender: Optional[bool] = None
    slow_network_ms: Optional[int] = None


# --------------------------------------------------------------------------- platform: auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    expires_in: int = 3600


class Me(BaseModel):
    user_id: str
    username: str
    display_name: str
    role: Role
    language: str = "ur"


# --------------------------------------------------------------------------- platform: cases
class CaseSummary(BaseModel):
    id: str
    citizen_name: str
    status: CaseStatus
    claim_type: str
    amount_claimed_pkr: int
    risk_score: float
    confidence: float
    assigned_to: Optional[str] = None
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    items: List[CaseSummary]
    total: int


class CaseCreate(BaseModel):
    citizen_name: str
    cnic: Optional[str] = None
    claim_type: str = "missing"
    amount_claimed_pkr: int = 0
    notes: Optional[str] = None


class CaseNote(BaseModel):
    author: str
    text: str
    created_at: str


class CaseDetail(CaseSummary):
    cnic_masked: str
    programme: str = "Sahara Relief Programme"
    notes: List[CaseNote] = Field(default_factory=list)
    decision: Optional[Dict[str, Any]] = None
    explanation_ur: Optional[str] = None
    explanation_en: Optional[str] = None
    pipeline_steps: List[Dict[str, Any]] = Field(default_factory=list)
    rule_version: Optional[int] = None


class AssignRequest(BaseModel):
    officer_id: str


class EscalateRequest(BaseModel):
    reason: str


class OfficerDecision(BaseModel):
    action: str = Field(..., description="approve | reject | request_more")
    note: Optional[str] = None


class CloseRequest(BaseModel):
    resolution: str


# --------------------------------------------------------------------------- platform: claims etc.
class ClaimCreate(BaseModel):
    transcript: Optional[str] = None
    cnic: Optional[str] = None
    document_id: Optional[str] = None
    on_behalf_of: Optional[str] = None


class ClaimResponse(BaseModel):
    claim_id: str
    case_id: str
    status: CaseStatus
    draft: Dict[str, Any]
    decision: Dict[str, Any]
    explanation_ur: str
    explanation_en: str
    pipeline_steps: List[Dict[str, Any]] = Field(default_factory=list)


class MessageCheckRequest(BaseModel):
    text: str
    sender: str


class MessageCheckResponse(BaseModel):
    label: MessageLabel
    confidence: float
    reasons: List[str]
    official_sender: bool
    explanation_ur: str
    explanation_en: str
    model_version: str


class DocumentResponse(BaseModel):
    document_id: str
    fields: Dict[str, str]
    blur_score: float
    format_ok: bool
    confidence: float
    retake_needed: bool
    explanation_ur: str
    explanation_en: str
    model_version: str


# --------------------------------------------------------------------------- platform: rules
class RuleSummary(BaseModel):
    id: str
    name: str
    current_version: int
    updated_at: str


class RuleListResponse(BaseModel):
    items: List[RuleSummary]


class RuleVersionsResponse(BaseModel):
    rule_id: str
    versions: List[RuleVersion]


class RuleVersionCreate(BaseModel):
    auto_handle_min: float
    ask_more_min: float
    red_flags: List[str] = Field(default_factory=list)
    logic: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None


# --------------------------------------------------------------------------- platform: consent
class ConsentRecord(BaseModel):
    id: str
    scope: ConsentScope
    granted: bool
    granted_at: Optional[str] = None
    withdrawn_at: Optional[str] = None
    shared_with: List[str] = Field(default_factory=list)
    purpose: str


class ConsentListResponse(BaseModel):
    items: List[ConsentRecord]


class ConsentGrant(BaseModel):
    scope: ConsentScope
    shared_with: List[str] = Field(default_factory=list)


class ConsentCorrection(BaseModel):
    field: str
    new_value: str


# --------------------------------------------------------------------------- platform: audit, queue
class AuditEntry(BaseModel):
    id: str
    timestamp: str
    actor: str
    actor_type: str = Field(..., description="user | ai | agent | system")
    action: str
    target: str
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None


class AuditListResponse(BaseModel):
    items: List[AuditEntry]
    total: int


class QueueItem(BaseModel):
    case_id: str
    citizen_name: str
    risk_score: float
    confidence: float
    recommended_action: DecisionAction
    reasons: List[str]
    waiting_since: str


class QueueResponse(BaseModel):
    items: List[QueueItem] = Field(..., description="Sorted: risk desc, then confidence asc")


class Family(BaseModel):
    family_id: str
    head_name: str
    case_count: int
    open_cases: int
    last_action: str
    consent_on_file: bool


class HelperFamiliesResponse(BaseModel):
    items: List[Family]


class ApiKeyRecord(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    created_at: str
    last_used_at: Optional[str] = None
    revoked: bool = False


class ApiKeyListResponse(BaseModel):
    items: List[ApiKeyRecord]


class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str] = Field(default_factory=list)


class EvalResults(BaseModel):
    model_version: str
    generated_at: str
    classifier: Dict[str, float]
    matching: Dict[str, float]
    decision: Dict[str, Any]
    cost_assumptions: Dict[str, int]
    total_cost: int
    confusion: Dict[str, Dict[str, int]]
