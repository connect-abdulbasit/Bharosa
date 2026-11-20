"""AI interface: the six functions /ai must implement, with Pydantic I/O models.

Rules (non-negotiable):
- Every output carries `confidence: float` (0..1, calibrated) and `model_version: str`.
- Pure functions: no DB, no HTTP (except the LLM call inside extract_claim/explain).
- Thresholds come from the RuleVersion passed in, never hard-coded.
- Never silently guess: low confidence -> ask_more / send_to_human.
Python 3.9 compatible.
"""
from typing import Any, Dict, List, Literal, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field

from contracts.enums import DecisionAction, MessageLabel
from contracts.schemas import Payment, PersonRecord, RuleVersion


# ------------------------------------------------------------------ 1. classify_message
class MessageVerdict(BaseModel):
    label: MessageLabel
    confidence: float = Field(..., ge=0, le=1)
    reasons: List[str]
    model_version: str


# ------------------------------------------------------------------ 2. match_person
class MatchResult(BaseModel):
    match_id: Optional[str] = Field(None, description="CNIC of best candidate, or None")
    score: float = Field(..., ge=0, le=1)
    variants: List[str] = Field(default_factory=list, description="Name variants considered")
    confidence: float = Field(..., ge=0, le=1)
    model_version: str


# ------------------------------------------------------------------ 3. extract_claim
class ClaimDraft(BaseModel):
    claimant_name: str
    cnic: Optional[str] = None
    programme: str = "Sahara Relief Programme"
    claim_type: Literal["missing", "short_paid"]
    amount_claimed_pkr: Optional[int] = None
    period: Optional[str] = None
    details: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    model_version: str


class ExtractionError(BaseModel):
    error: str
    reason: str
    missing_fields: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    model_version: str


# ------------------------------------------------------------------ 4. read_document
class DocumentReading(BaseModel):
    fields: Dict[str, str]
    blur_score: float = Field(..., ge=0, le=1, description="0 sharp .. 1 unreadable")
    format_ok: bool
    confidence: float = Field(..., ge=0, le=1)
    model_version: str


# ------------------------------------------------------------------ 5. decide
class Evidence(BaseModel):
    verdict: Optional[MessageVerdict] = None
    match: Optional[MatchResult] = None
    document: Optional[DocumentReading] = None
    ledger: List[Payment] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    payment_step: bool = False
    mock_failures: List[str] = Field(default_factory=list)


class Decision(BaseModel):
    action: DecisionAction
    confidence: float = Field(..., ge=0, le=1)
    reasons: List[str]
    trace: Dict[str, Any]
    rule_version: int
    requires_officer_approval: bool = Field(
        True, description="Always True when a payment step is involved"
    )
    model_version: str


# ------------------------------------------------------------------ 6. explain
# explain(trace, lang) -> str  (plain language, Urdu or English)


@runtime_checkable
class BharosaAI(Protocol):
    def classify_message(self, text: str, sender: str) -> MessageVerdict: ...

    def match_person(
        self, name: str, cnic: Optional[str], candidates: List[PersonRecord]
    ) -> MatchResult: ...

    def extract_claim(self, transcript: str) -> Union[ClaimDraft, ExtractionError]: ...

    def read_document(self, image_bytes: bytes) -> DocumentReading: ...

    def decide(self, claim: ClaimDraft, evidence: Evidence, rule: RuleVersion) -> Decision: ...

    def explain(self, trace: Dict[str, Any], lang: Literal["ur", "en"]) -> str: ...
