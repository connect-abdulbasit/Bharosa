"""Evaluation: what the system has actually done (decisions, overrides, confidence, speed) + the AI model eval, if present."""
import json
from collections import Counter, defaultdict
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.config import settings
from app.db import get_db
from app.models import CheckedMessage, Decision, Job
from app.routing import CompactRoute
from contracts.enums import Role
from contracts.schemas import LiveEvalResults

router = APIRouter(tags=["eval"], route_class=CompactRoute)
HUMAN = {"approve", "reject", "ask_more"}  # officer actions (AI actions are auto_handle / ask_more / send_to_human)


def _avg(xs) -> Any:
    xs = list(xs)
    return round(sum(xs) / len(xs), 3) if xs else None


@router.get("/eval", response_model=LiveEvalResults, summary="Evaluation numbers from stored decisions and checks")
def evaluation(user=Depends(require_role(Role.officer, Role.admin, Role.auditor)), db: Session = Depends(get_db)):
    """Computed live from the database: decisions by action, how often officers overrode the AI, average confidence,
    average pipeline time and scam-check totals. Includes `ai/eval/eval_results.json` as `model_eval` when it exists."""
    decisions = db.execute(select(Decision).order_by(Decision.created_at)).scalars().all()
    ai_rows = [d for d in decisions if d.decided_by in ("ai",)]
    agent_rows = [d for d in decisions if d.decided_by in ("agent", "system")]
    officer_rows = [d for d in decisions if d.action in HUMAN and d.decided_by not in ("ai", "agent", "system")]

    # Officer vs AI: compare each officer decision with the latest AI decision on the same case made before it.
    last_ai: Dict[str, Decision] = {}
    pairs: Counter = Counter()
    overrides = 0
    compared = 0
    for d in decisions:
        if d.decided_by == "ai":
            last_ai[d.case_id] = d
        elif d in officer_rows and d.case_id in last_ai:
            ai = last_ai[d.case_id]
            compared += 1
            pairs["%s -> %s" % (ai.action, d.action)] += 1
            if ai.action == "auto_handle" and d.action != "approve":  # AI wanted to go ahead, the officer stopped it
                overrides += 1

    by_conf: Dict[str, list] = defaultdict(list)
    for d in ai_rows:
        by_conf[d.action].append(d.confidence)
    by_rule = Counter("%s v%s" % (d.rule_id, d.rule_version) for d in decisions if d.rule_version)

    jobs = db.execute(select(Job).where(Job.status == "done", Job.started_at.isnot(None), Job.finished_at.isnot(None))).scalars().all()
    seconds = []
    for j in jobs:
        a, b = j.started_at, j.finished_at
        if a and b:
            seconds.append(max((b.replace(tzinfo=None) - a.replace(tzinfo=None)).total_seconds(), 0.0))

    msgs = db.execute(select(CheckedMessage)).scalars().all()
    model_eval = None
    try:
        if settings.EVAL_RESULTS_PATH.exists():
            model_eval = json.loads(settings.EVAL_RESULTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        model_eval = None

    return {
        "decisions": {"total": len(decisions), "ai_total": len(ai_rows), "agent_total": len(agent_rows), "officer_total": len(officer_rows),
                      "by_action": dict(Counter(d.action for d in ai_rows)), "officer_by_action": dict(Counter(d.action for d in officer_rows)),
                      "by_rule_version": dict(by_rule)},
        "officer_vs_ai": {"compared": compared, "overrides": overrides,
                          "override_rate": round(overrides / compared, 3) if compared else None, "pairs": dict(pairs)},
        "confidence": {"ai_average": _avg(d.confidence for d in ai_rows),
                       "by_action": {k: _avg(v) for k, v in by_conf.items()}},
        "pipeline": {"runs": len(seconds), "average_seconds": _avg(seconds), "max_seconds": round(max(seconds), 3) if seconds else None},
        "messages": {"total": len(msgs), "by_label": dict(Counter(m.label for m in msgs)), "average_confidence": _avg(m.confidence for m in msgs)},
        "model_eval": model_eval,
    }
