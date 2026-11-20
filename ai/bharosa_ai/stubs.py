"""Stub implementations: deterministic, realistic, always include confidence + model_version.

The stubs are intentionally simple but behave sensibly so backend/frontend can integrate:
- obvious scam cues -> scam; official sender 9090 -> genuine; otherwise unsure
- decide() really applies the decision rule from the RuleVersion it is given.
"""
import re
from typing import Any, Dict, List, Literal, Optional, Union

from contracts.ai_interface import (
    ClaimDraft,
    Decision,
    DocumentReading,
    Evidence,
    ExtractionError,
    MatchResult,
    MessageVerdict,
)
from contracts.enums import DecisionAction, MessageLabel
from contracts.schemas import PersonRecord, RuleVersion

MODEL_VERSION = "stub-0.1"
OFFICIAL_SENDER = "9090"
SCAM_CUES = ["http", "bit.ly", "fee", "advance", "send money", "urgent", "otp", "pin", "fees", "فیس"]


def classify_message(text: str, sender: str) -> MessageVerdict:
    lowered = text.lower()
    hits = [c for c in SCAM_CUES if c in lowered]
    reasons: List[str] = []
    if sender.strip() != OFFICIAL_SENDER:
        reasons.append("Sender '%s' is not the official code %s" % (sender, OFFICIAL_SENDER))
    reasons.extend("Contains suspicious cue '%s'" % h for h in hits)
    if hits and sender.strip() != OFFICIAL_SENDER:
        return MessageVerdict(label=MessageLabel.scam, confidence=0.96, reasons=reasons, model_version=MODEL_VERSION)
    if sender.strip() == OFFICIAL_SENDER and not hits:
        return MessageVerdict(
            label=MessageLabel.genuine, confidence=0.93,
            reasons=["Sent from official code %s" % OFFICIAL_SENDER], model_version=MODEL_VERSION)
    return MessageVerdict(
        label=MessageLabel.unsure, confidence=0.55,
        reasons=reasons or ["Not enough evidence either way"], model_version=MODEL_VERSION)


def _norm(name: str) -> str:
    name = name.lower().replace("mohammad", "muhammad").replace("mohammed", "muhammad")
    return re.sub(r"[^a-z ]", "", name).strip()


def match_person(name: str, cnic: Optional[str], candidates: List[PersonRecord]) -> MatchResult:
    variants = sorted({name, _norm(name).title()})
    if cnic:
        for c in candidates:
            if c.cnic == cnic:
                return MatchResult(match_id=c.cnic, score=0.97, confidence=0.97, variants=variants, model_version=MODEL_VERSION)
    target = _norm(name)
    best, best_score = None, 0.0
    for c in candidates:
        names = [c.full_name] + list(c.aliases)
        score = max(_overlap(target, _norm(n)) for n in names)
        if score > best_score:
            best, best_score = c, score
    if best is None or best_score < 0.6:
        return MatchResult(match_id=None, score=best_score, confidence=0.4, variants=variants, model_version=MODEL_VERSION)
    return MatchResult(match_id=best.cnic, score=round(best_score, 2), confidence=round(best_score * 0.95, 2),
                       variants=variants, model_version=MODEL_VERSION)


def _overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def extract_claim(transcript: str) -> Union[ClaimDraft, ExtractionError]:
    if not transcript or len(transcript.strip()) < 10:
        return ExtractionError(error="transcript_too_short", reason="Not enough speech to understand the claim",
                               missing_fields=["claimant_name", "claim_type"], model_version=MODEL_VERSION)
    short = any(w in transcript.lower() for w in ["kam", "short", "less", "کم"])
    return ClaimDraft(
        claimant_name="Mohammad Aslam", cnic=None, claim_type="short_paid" if short else "missing",
        amount_claimed_pkr=4000 if short else 12000, period="2026-10", details=transcript[:200],
        confidence=0.81, model_version=MODEL_VERSION)


def read_document(image_bytes: bytes) -> DocumentReading:
    if not image_bytes or len(image_bytes) < 100:
        return DocumentReading(fields={}, blur_score=1.0, format_ok=False, confidence=0.1, model_version=MODEL_VERSION)
    return DocumentReading(
        fields={"name": "Muhammad Aslam", "cnic": "0000042101001", "father_name": "Abdul Rehman"},
        blur_score=0.18, format_ok=True, confidence=0.86, model_version=MODEL_VERSION)


def decide(claim: ClaimDraft, evidence: Evidence, rule: RuleVersion) -> Decision:
    parts = [claim.confidence]
    if evidence.match is not None:
        parts.append(evidence.match.confidence)
    if evidence.document is not None:
        parts.append(evidence.document.confidence)
    if evidence.verdict is not None:
        parts.append(evidence.verdict.confidence)
    confidence = round(min(parts), 2)  # conservative: weakest link
    flags = list(evidence.red_flags) + ["mock_service_failure" for _ in evidence.mock_failures[:1]]
    reasons: List[str] = []
    if flags:
        action = DecisionAction.send_to_human
        reasons.append("Red flags present: %s" % ", ".join(flags))
    elif confidence >= rule.auto_handle_min:
        action = DecisionAction.auto_handle
        reasons.append("Confidence %.2f >= %.2f and no red flags" % (confidence, rule.auto_handle_min))
    elif confidence >= rule.ask_more_min:
        action = DecisionAction.ask_more
        reasons.append("Confidence %.2f is between %.2f and %.2f: need more proof" % (confidence, rule.ask_more_min, rule.auto_handle_min))
    else:
        action = DecisionAction.send_to_human
        reasons.append("Confidence %.2f below %.2f" % (confidence, rule.ask_more_min))
    trace: Dict[str, Any] = {
        "combined_confidence": confidence, "components": parts, "red_flags": flags,
        "thresholds": {"auto_handle_min": rule.auto_handle_min, "ask_more_min": rule.ask_more_min},
        "payment_step": evidence.payment_step,
    }
    return Decision(action=action, confidence=confidence, reasons=reasons, trace=trace, rule_version=rule.version,
                    requires_officer_approval=True, model_version=MODEL_VERSION)


_EXPLAIN = {
    DecisionAction.auto_handle.value: (
        "آپ کی درخواست درست لگتی ہے۔ ہم اسے آگے بڑھا رہے ہیں۔ ادائیگی سے پہلے افسر منظوری دے گا۔",
        "Your request looks correct and is moving forward. An officer must still approve any payment."),
    DecisionAction.ask_more.value: (
        "ہمیں تھوڑی اور معلومات چاہییں۔ براہ کرم شناختی کارڈ کی صاف تصویر بھیجیں۔",
        "We need a little more information. Please send a clear photo of your ID card."),
    DecisionAction.send_to_human.value: (
        "ہم نے آپ کا کیس افسر کو بھیج دیا ہے۔ وہ آپ سے رابطہ کریں گے۔",
        "We have sent your case to an officer, who will contact you."),
}


def explain(trace: Dict[str, Any], lang: Literal["ur", "en"]) -> str:
    action = trace.get("action", DecisionAction.send_to_human.value)
    ur, en = _EXPLAIN.get(action, _EXPLAIN[DecisionAction.send_to_human.value])
    return ur if lang == "ur" else en
