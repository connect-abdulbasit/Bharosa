"""Claim agent pipeline. Started by POST /claims, continued by POST /claims/{id}/resume.

Steps (each saved to the case: `current_step`, and to claims.data["pipeline"]), so a failure or a dropped
connection resumes where it stopped instead of starting over:

  extract_claim -> read_document -> identity_lookup -> ledger_lookup -> match_person -> decide -> explain -> notify

Rules:
- every step writes an audit entry (actor_type 'ai' for AI functions, 'agent' for orchestration/mocks) with an
  input summary, output, confidence and model_version;
- consent.require() runs BEFORE every identity / ledger call (it logs + commits blocked attempts);
- a mock timeout/error, missing consent or an unexpected bug NEVER becomes a 500: progress is saved, the case goes
  to `with_officer` with a note saying exactly what failed, and the normal response is returned;
- decide mapping: auto_handle -> approved ONLY when no payment is needed, otherwise with_officer (a payment always
  needs an officer); ask_more -> needs_more_proof (+ what is needed); send_to_human -> with_officer;
- duplicate protection: one open claim per citizen per month; a second one is flagged and sent to an officer.
"""
import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import bharosa_ai as ai
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Case, Claim, Decision, Document, User
from app.services import audit
from app.services import cases as case_service
from app.services import consent as consent_service
from app.services.consent import ConsentRequired
from app.services.mock_errors import MockUnavailable
from app.services.serialize import case_detail
from contracts.ai_interface import ClaimDraft, DocumentReading, Evidence, ExtractionError, MatchResult
from contracts.enums import ConsentScope
from contracts.schemas import Payment, PersonRecord, RuleVersion

log = logging.getLogger("bharosa.pipeline")

PROGRAMME_AMOUNT = 12000  # PKR per month in the fictional Sahara Relief Programme
STEPS = ["extract_claim", "read_document", "identity_lookup", "ledger_lookup", "match_person", "decide", "explain", "notify"]
CLOSED_FOR_DUPLICATES = ("closed", "rejected")
BLUR_RETAKE = 0.5
STATUS_FOR = {"ask_more": "needs_more_proof", "send_to_human": "with_officer"}
GENERIC_NEEDS = ["A clear photo of your ID card, or more details about the missing payment"]


class Terminal(Exception):
    """A normal, final outcome reached before the decide step (ask for more / send to a human)."""

    def __init__(self, action: str, reasons: List[str], needs: Optional[List[str]] = None, flags: Optional[List[str]] = None,
                 confidence: float = 0.0, model_version: Optional[str] = None):
        super().__init__(reasons[0] if reasons else action)
        self.action, self.reasons, self.needs, self.flags = action, reasons, needs or [], flags or []
        self.confidence, self.model_version = confidence, model_version


@dataclass
class Ctx:
    db: Session
    actor: User
    citizen: User
    case: Case
    claim: Claim
    mocks: Any
    rule: RuleVersion
    state: Dict[str, Any]


# --------------------------------------------------------------------------- state + audit helpers
def new_state() -> Dict[str, Any]:
    return {"completed": [], "outputs": {}, "current": None, "failed": None, "finished": False, "needs": [],
            "flags_found": [], "payment_needed": False, "shortfall": 0}


def _save(ctx: Ctx) -> None:
    # deep copies so SQLAlchemy sees a NEW value (in-place mutation of JSON is not tracked)
    ctx.claim.data = copy.deepcopy(dict(ctx.claim.data or {}, pipeline=ctx.state))
    ctx.db.flush()


def _audit(ctx: Ctx, kind: str, step: str, inp: Dict[str, Any], out: Dict[str, Any], confidence: Optional[float] = None,
           model_version: Optional[str] = None) -> None:
    audit.log(ctx.db, "ai" if kind == "ai" else "agent", ("ai:%s" % step) if kind == "ai" else "agent:pipeline",
              "%s.%s" % (kind, step), "case", ctx.case.id,
              after={"step": step, "input": inp, "output": out, "confidence": confidence, "model_version": model_version,
                     "requested_by": ctx.actor.id, "citizen_id": ctx.citizen.id})


def _risk(flags: List[str], confidence: float) -> float:
    return round(min(1.0, 0.25 * len(flags) + 0.5 * (1.0 - confidence)), 2)


def _active_decision_rule(ctx: Ctx) -> Dict[str, Any]:
    return {"rule_id": ctx.rule.rule_id, "rule_version": ctx.rule.version}


# --------------------------------------------------------------------------- finishing the run
def _move(ctx: Ctx, status: str, note: str) -> None:
    if ctx.case.status != status:
        case_service.change_status(ctx.db, ctx.case, status, ctx.actor, "case.pipeline_status", note=note, step=ctx.case.current_step)
    else:
        case_service.add_note(ctx.case, "agent:pipeline", note)


def _explain(ctx: Ctx, action: str, trace: Dict[str, Any], needs: List[str], confidence: float = 0.0,
             model_version: Optional[str] = None) -> Dict[str, str]:
    t = dict(trace, action=action)
    ur, en = ai.explain(t, "ur"), ai.explain(t, "en")
    if needs:
        en = "%s We need: %s." % (en, "; ".join(needs))
    _audit(ctx, "ai", "explain", {"action": action}, {"chars_ur": len(ur), "chars_en": len(en)}, confidence,
           model_version or "%s-explain" % settings.AI_MODE)
    return {"explanation_ur": ur, "explanation_en": en}


def finalize(ctx: Ctx, action: str, reasons: List[str], needs: List[str], flags: List[str], confidence: float,
             decided_by: str, finished: bool, model_version: Optional[str] = None, note: Optional[str] = None,
             extra_trace: Optional[Dict[str, Any]] = None) -> Decision:
    """Record a decision for an early/terminal outcome (no decide step) and move the case."""
    trace = dict(extra_trace or {}, needs=needs, flags=flags, terminal=True)
    trace.update(_explain(ctx, action, trace, needs, confidence, model_version))
    dec = Decision(case_id=ctx.case.id, action=action, confidence=confidence, reasons=reasons, trace=trace,
                   model_version=model_version, decided_by=decided_by, **_active_decision_rule(ctx))
    ctx.db.add(dec)
    ctx.case.confidence = confidence
    ctx.case.risk_score = max(ctx.case.risk_score or 0.0, _risk(flags, confidence))
    _move(ctx, STATUS_FOR[action], note or ("; ".join(reasons)))
    ctx.state["finished"] = finished
    ctx.state["needs"] = needs
    ctx.state["current"] = ctx.case.current_step = ("completed" if finished else ctx.state.get("current"))
    ctx.db.flush()
    audit.log(ctx.db, "agent", "agent:pipeline", "agent.terminal_decision", "case", ctx.case.id,
              after={"action": action, "reasons": reasons, "needs": needs, "flags": flags, "finished": finished,
                     "rule_id": ctx.rule.rule_id, "rule_version": ctx.rule.version})
    _save(ctx)
    ctx.db.commit()
    return dec


def _fail(ctx: Ctx, step: str, message: str) -> None:
    """Pause: save progress, send to an officer with a precise note. Resumable with POST /claims/{id}/resume."""
    ctx.db.rollback()  # drop any half-done step; completed steps were committed
    ctx.state["failed"] = {"step": step, "reason": message}
    ctx.state["current"] = step
    ctx.case.current_step = step
    note = "Pipeline paused at step '%s': %s Progress is saved; resume after fixing, or review manually." % (step, message)
    finalize(ctx, "send_to_human", [message], ctx.state.get("needs", []), ["mock_service_failure"], 0.0, "agent", finished=False,
             note=note, extra_trace={"failed_step": step})


# --------------------------------------------------------------------------- step handlers
def _open_duplicate(ctx: Ctx) -> Optional[Case]:
    if not ctx.claim.month:
        return None
    stmt = (select(Case).join(Claim, Claim.case_id == Case.id)
            .where(Case.citizen_id == ctx.citizen.id, Claim.month == ctx.claim.month, Case.id != ctx.case.id,
                   Case.status.notin_(CLOSED_FOR_DUPLICATES)).order_by(Case.created_at))
    return ctx.db.execute(stmt).scalars().first()


def step_extract_claim(ctx: Ctx) -> Dict[str, Any]:
    transcript = ctx.claim.transcript or ""
    res = ai.extract_claim(transcript)
    if isinstance(res, ExtractionError):
        _audit(ctx, "ai", "extract_claim", {"transcript_chars": len(transcript)}, {"error": res.error, "reason": res.reason},
               res.confidence, res.model_version)
        raise Terminal("ask_more", ["We could not understand the problem from what was said (%s)." % res.reason],
                       needs=["Tell us the problem again, slowly and clearly"], confidence=res.confidence, model_version=res.model_version)
    draft = res.model_dump(mode="json")
    ctx.claim.claim_type = res.claim_type
    ctx.claim.month = res.period
    ctx.claim.expected_amount = res.amount_claimed_pkr or 0
    _audit(ctx, "ai", "extract_claim", {"transcript_chars": len(transcript)},
           {"claim_type": res.claim_type, "month": res.period, "amount": res.amount_claimed_pkr, "name": res.claimant_name},
           res.confidence, res.model_version)
    dup = _open_duplicate(ctx)
    if dup is not None:
        _audit(ctx, "agent", "duplicate_check", {"month": ctx.claim.month}, {"duplicate_of": dup.id})
        raise Terminal("send_to_human", ["Duplicate claim: this citizen already has an open claim for %s (case %s)." % (ctx.claim.month, dup.id)],
                       flags=["duplicate_claim"], confidence=res.confidence, model_version=res.model_version)
    return {"draft": draft}


def step_read_document(ctx: Ctx) -> Dict[str, Any]:
    doc_id = (ctx.claim.data or {}).get("document_id")
    if not doc_id:
        _audit(ctx, "agent", "read_document", {}, {"skipped": "no ID photo uploaded"})
        return {"skipped": True, "usable": False}
    doc = ctx.db.get(Document, doc_id)
    path = settings.UPLOAD_DIR / doc.file_path if doc and doc.file_path else None
    if doc is None or path is None or not path.exists():
        ctx.state["needs"].append("Upload the ID card photo again (we could not open the saved file)")
        return {"skipped": True, "usable": False, "error": "file missing"}
    reading = ai.read_document(path.read_bytes())
    doc.case_id = ctx.case.id
    doc.ocr_fields, doc.blur_score, doc.format_ok, doc.confidence = reading.fields, reading.blur_score, reading.format_ok, reading.confidence
    usable = reading.blur_score <= BLUR_RETAKE and reading.format_ok
    if not usable:
        ctx.state["needs"].append("Retake the ID card photo: it is blurry or unreadable")
    _audit(ctx, "ai", "read_document", {"document_id": doc_id}, {"blur_score": reading.blur_score, "format_ok": reading.format_ok,
           "usable": usable, "fields_read": sorted(reading.fields)}, reading.confidence, reading.model_version)
    return {"usable": usable, "reading": reading.model_dump(mode="json")}


def step_identity_lookup(ctx: Ctx) -> Dict[str, Any]:
    cnic = ctx.citizen.cnic  # ONLY the account's own ID number: nobody can look up someone else's record
    if not cnic:
        raise Terminal("send_to_human", ["No ID number is on file for this account, so identity cannot be checked."],
                       needs=["An officer must add the ID number"], flags=["mock_service_failure"])
    consent_service.require(ctx.db, ctx.citizen.id, ConsentScope.identity, ctx.actor, "claim: identity lookup")
    rec = ctx.mocks.identity(cnic)
    _audit(ctx, "agent", "identity_lookup", {"cnic_masked": cnic[:5] + "*" * 7 + cnic[-1]}, {"found": True, "full_name": rec.get("full_name"),
           "simulated": rec.get("simulated")})
    return {"record": rec}


def step_ledger_lookup(ctx: Ctx) -> Dict[str, Any]:
    cnic = ctx.citizen.cnic
    consent_service.require(ctx.db, ctx.citizen.id, ConsentScope.payments, ctx.actor, "claim: payment ledger lookup")
    led = ctx.mocks.ledger(cnic)
    month = ctx.claim.month
    payments = [p for p in led.get("payments", []) if not month or str(p.get("date", "")).startswith(month)]
    seen, unique, flags = set(), [], []
    for p in payments:
        key = (p.get("date"), p.get("amount_pkr"), p.get("agent_id"))
        if key in seen:
            if "duplicate_payment" not in flags:
                flags.append("duplicate_payment")
            continue
        seen.add(key)
        unique.append(p)
    received = sum(int(p.get("amount_pkr", 0)) for p in unique)
    if 0 < received < PROGRAMME_AMOUNT:
        flags.append("short_payment")
    if received >= PROGRAMME_AMOUNT or (received == 0 and ctx.claim.claim_type == "short_paid"):
        flags.append("claim_contradicts_ledger")
    shortfall = max(PROGRAMME_AMOUNT - received, 0)
    ctx.claim.expected_amount, ctx.claim.received_amount = PROGRAMME_AMOUNT, received
    ctx.state.update(flags_found=flags, shortfall=shortfall, payment_needed=shortfall > 0 and "claim_contradicts_ledger" not in flags)
    _audit(ctx, "agent", "ledger_lookup", {"month": month}, {"payments": len(unique), "received": received, "shortfall": shortfall, "flags": flags})
    return {"payments": unique, "received": received, "shortfall": shortfall, "flags": flags}


def step_match_person(ctx: Ctx) -> Dict[str, Any]:
    draft = ctx.state["outputs"]["extract_claim"]["draft"]
    record = ctx.state["outputs"]["identity_lookup"]["record"]
    candidate = PersonRecord(**{k: v for k, v in record.items() if k in PersonRecord.model_fields})
    # cnic=None on purpose: the ID number was already used to fetch this record; this checks the NAME is consistent.
    res = ai.match_person(draft["claimant_name"], None, [candidate])
    _audit(ctx, "ai", "match_person", {"claimed_name": draft["claimant_name"]},
           {"matched": res.match_id is not None, "score": res.score, "variants": res.variants}, res.confidence, res.model_version)
    return {"match": res.model_dump(mode="json")}


def map_decision(action: str, payment_needed: bool, needs: List[str]) -> Dict[str, Any]:
    """AI action -> case status. A payment ALWAYS needs an officer."""
    if action == "auto_handle":
        if needs:
            return {"status": "needs_more_proof", "why": "AI would handle this, but proof is still missing"}
        if payment_needed:
            return {"status": "with_officer", "why": "AI would handle this automatically, but a payment always needs officer approval"}
        return {"status": "approved", "why": "Confidence is high, no red flags and no payment is needed"}
    if action == "ask_more":
        return {"status": "needs_more_proof", "why": "Confidence is not high enough: more proof is needed"}
    return {"status": "with_officer", "why": "Low confidence or red flags: a person must check"}


def step_decide(ctx: Ctx) -> Dict[str, Any]:
    out = ctx.state["outputs"]
    draft = ClaimDraft(**out["extract_claim"]["draft"])
    doc_out = out.get("read_document", {})
    reading = DocumentReading(**doc_out["reading"]) if doc_out.get("usable") else None
    ledger = [Payment(**{k: v for k, v in p.items() if k in Payment.model_fields}) for p in out["ledger_lookup"]["payments"]]
    # Flags the ACTIVE RULE cares about; the agent never invents flags the rule ignores.
    flags = [f for f in ctx.state["flags_found"] if f in ctx.rule.red_flags]
    evidence = Evidence(match=MatchResult(**out["match_person"]["match"]), document=reading, ledger=ledger,
                        red_flags=flags, payment_step=ctx.state["payment_needed"])
    dec = ai.decide(draft, evidence, ctx.rule)
    action = dec.action.value
    needs = list(ctx.state["needs"])
    mapped = map_decision(action, ctx.state["payment_needed"], needs)
    if mapped["status"] == "needs_more_proof" and not needs:
        needs = list(GENERIC_NEEDS)
    reasons = list(dec.reasons)
    if ctx.state["payment_needed"]:
        reasons.append("A payment of PKR %d is involved: an officer must approve it." % ctx.state["shortfall"])
    trace = dict(dec.trace, needs=needs, flags=flags, flags_found=ctx.state["flags_found"], payment_needed=ctx.state["payment_needed"],
                 shortfall=ctx.state["shortfall"], ai_action=action, mapped_status=mapped["status"], why=mapped["why"])
    row = Decision(case_id=ctx.case.id, action=action, confidence=dec.confidence, reasons=reasons, trace=trace,
                   model_version=dec.model_version, decided_by="ai", rule_id=ctx.rule.rule_id, rule_version=dec.rule_version)
    ctx.db.add(row)
    ctx.case.confidence = dec.confidence
    ctx.case.risk_score = _risk(flags, dec.confidence)
    ctx.state["needs"] = needs
    note = "AI decision %s (confidence %.2f, rule v%s): %s." % (action, dec.confidence, dec.rule_version, mapped["why"])
    if needs and mapped["status"] == "needs_more_proof":
        note += " Needed: %s." % "; ".join(needs)
    _move(ctx, mapped["status"], note)
    ctx.db.flush()
    ctx.state["decision_id"] = row.id  # id is assigned on flush
    _audit(ctx, "ai", "decide", {"claim_confidence": draft.confidence, "flags": flags, "payment_step": ctx.state["payment_needed"]},
           {"action": action, "status": mapped["status"], "rule_id": ctx.rule.rule_id, "rule_version": dec.rule_version, "reasons": reasons},
           dec.confidence, dec.model_version)
    return {"action": action, "confidence": dec.confidence, "status": mapped["status"], "rule_version": dec.rule_version}


def step_explain(ctx: Ctx) -> Dict[str, Any]:
    row = ctx.db.get(Decision, ctx.state["decision_id"])
    texts = _explain(ctx, row.action, row.trace, ctx.state["needs"] if row.action != "send_to_human" else [], row.confidence, row.model_version)
    row.trace = dict(row.trace, **texts)
    return {"explained": True}


def step_notify(ctx: Ctx) -> Dict[str, Any]:
    c = consent_service.get_consent(ctx.db, ctx.citizen.id, ConsentScope.notifications)
    if c is None or c.status != "granted":
        _audit(ctx, "agent", "notify", {}, {"skipped": "no consent for notifications"})
        return {"sent": False, "skipped": "no consent for notifications"}
    row = ctx.db.get(Decision, ctx.state["decision_id"])
    msg = row.trace.get("explanation_ur", "") or row.trace.get("explanation_en", "")
    try:
        res = ctx.mocks.notify(ctx.citizen.phone or "unknown", msg[:300])
    except MockUnavailable as exc:  # not critical: the decision stands
        case_service.add_note(ctx.case, "agent:pipeline", "Could not send the SMS update (%s). The decision is unchanged." % exc)
        _audit(ctx, "agent", "notify", {}, {"sent": False, "error": str(exc)[:200]})
        return {"sent": False, "error": str(exc)[:200]}
    _audit(ctx, "agent", "notify", {"channel": "sms"}, {"sent": True, "message_id": res.get("message_id")})
    return {"sent": True, "message_id": res.get("message_id")}


HANDLERS = {
    "extract_claim": step_extract_claim, "read_document": step_read_document, "identity_lookup": step_identity_lookup,
    "ledger_lookup": step_ledger_lookup, "match_person": step_match_person, "decide": step_decide,
    "explain": step_explain, "notify": step_notify,
}


# --------------------------------------------------------------------------- orchestration
def run(ctx: Ctx) -> None:
    """Run (or resume) the pipeline. Never raises for step problems: it pauses and hands over to an officer."""
    ctx.state["failed"] = None
    step = ctx.state.get("current") or STEPS[0]
    try:
        for step in STEPS:
            if step in ctx.state["completed"]:
                continue
            ctx.state["current"] = ctx.case.current_step = step
            _save(ctx)
            ctx.db.commit()  # progress is durable before the step runs
            out = HANDLERS[step](ctx)
            ctx.state["outputs"][step] = out
            ctx.state["completed"].append(step)
            _save(ctx)
            ctx.db.commit()
        ctx.state.update(finished=True, current="completed")
        ctx.case.current_step = "completed"
        _save(ctx)
        ctx.db.commit()
    except Terminal as t:
        ctx.db.rollback()
        ctx.state["stopped"] = {"step": step, "reason": t.reasons[0] if t.reasons else t.action}
        finalize(ctx, t.action, t.reasons, t.needs, t.flags, t.confidence, "agent", finished=True, model_version=t.model_version)
    except ConsentRequired as exc:
        _fail(ctx, step, "Consent for '%s' is withdrawn or was never given, so this check was not done." % exc.scope)
    except MockUnavailable as exc:
        label = {"identity_lookup": "Identity lookup", "ledger_lookup": "Payment ledger lookup", "notify": "Notification"}.get(step, step)
        _fail(ctx, step, "%s failed: %s." % (label, str(exc)[:200]))
    except Exception:  # a bug must not become a 500 for a citizen
        log.exception("pipeline crashed at step %s", step)
        _fail(ctx, step, "An unexpected internal error occurred in step '%s'." % step)


def load_state(claim: Claim) -> Dict[str, Any]:
    return copy.deepcopy((claim.data or {}).get("pipeline") or new_state())


def make_ctx(db: Session, actor: User, citizen: User, case: Case, claim: Claim, mocks: Any, rule: RuleVersion) -> Ctx:
    return Ctx(db=db, actor=actor, citizen=citizen, case=case, claim=claim, mocks=mocks, rule=rule, state=load_state(claim))


def create(db: Session, actor: User, citizen: User, transcript: Optional[str], document_id: Optional[str]):
    """Save the input: case + claim (+ audit), committed. The pipeline itself is run by a background job."""
    case = Case(citizen_id=citizen.id, created_by=actor.id, status="submitted", current_step="queued", notes=[])
    db.add(case)
    db.flush()
    claim = Claim(case_id=case.id, claim_type="missing", expected_amount=0, received_amount=0, transcript=transcript,
                  data={"document_id": document_id, "pipeline": new_state()})
    db.add(claim)
    db.flush()
    audit.log(db, "user", actor.id, "case.create", "case", case.id, before=None,
              after={"status": "submitted", "citizen_id": citizen.id, "via": "claim_pipeline"})
    audit.log(db, "user", actor.id, "claim.create", "claim", claim.id, after={"case_id": case.id, "citizen_id": citizen.id,
              "has_document": bool(document_id)})
    return case, claim


def can_resume(case: Case, claim: Claim) -> bool:
    return not load_state(claim).get("finished") and case.status not in ("approved", "rejected", "closed")


# --------------------------------------------------------------------------- responses
def steps_view(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    failed = (state.get("failed") or {}).get("step")
    stopped = state.get("stopped") or {}
    out = []
    for s in STEPS:
        if s in state.get("completed", []):
            status, detail = "done", ""
            o = state.get("outputs", {}).get(s, {})
            if s == "decide":
                detail = "%s (confidence %.2f)" % (o.get("action"), o.get("confidence", 0))
            elif s == "ledger_lookup":
                detail = "received PKR %s, shortfall PKR %s" % (o.get("received"), o.get("shortfall"))
            elif o.get("skipped"):
                detail = str(o.get("skipped"))
        elif s == stopped.get("step"):
            status, detail = "stopped", stopped.get("reason", "")  # ended here on purpose (e.g. duplicate, unclear speech)
        elif s == failed:
            status, detail = "failed", (state.get("failed") or {}).get("reason", "")
        else:
            status, detail = "pending", ""
        out.append({"step": s, "status": status, "detail": detail})
    return out


def response(db: Session, case: Case, claim: Claim) -> Dict[str, Any]:
    d = case_detail(db, case)
    state = (claim.data or {}).get("pipeline", {})
    draft = state.get("outputs", {}).get("extract_claim", {}).get("draft", {})
    return {"claim_id": claim.id, "case_id": case.id, "status": case.status, "draft": draft,
            "decision": d["decision"] or {}, "explanation_ur": d["explanation_ur"] or "", "explanation_en": d["explanation_en"] or "",
            "pipeline_steps": steps_view(state)}


def progress(case: Case, claim: Claim, job_status: Optional[str]) -> Dict[str, Any]:
    """Small, cheap payload for polling (pairs with ETag)."""
    state = (claim.data or {}).get("pipeline", {})
    steps = steps_view(state)
    done = sum(1 for x in steps if x["status"] == "done")
    out: Dict[str, Any] = {"claim_id": claim.id, "case_id": case.id, "status": case.status, "current_step": case.current_step or "queued",
                           "finished": bool(state.get("finished")), "steps_done": done, "steps_total": len(STEPS),
                           "steps": [{"step": x["step"], "status": x["status"]} for x in steps], "job": job_status,
                           "active": job_status in ("queued", "running")}  # keep polling while True; False = settled (done, paused or failed)
    if state.get("failed"):
        out["failed"] = state["failed"]
    if state.get("stopped"):
        out["stopped"] = state["stopped"]
    return out
