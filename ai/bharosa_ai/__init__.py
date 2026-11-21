"""Bharosa AI package. Exports the six contract functions.

AI_MODE=stub (default) -> fixed realistic outputs from stubs.py
AI_MODE=real           -> the real implementations: classify.py (+ classify_ml.py), matching.py, extract.py
                          (+ llm.py), document.py (+ ocr.py, idcard.py), decide.py, explain.py. All six exist.
"""
import os

AI_MODE = os.environ.get("AI_MODE", "stub").lower()

if AI_MODE == "real":
    from bharosa_ai.classify import classify_message
    from bharosa_ai.decide import decide
    from bharosa_ai.document import read_document
    from bharosa_ai.explain import explain
    from bharosa_ai.extract import extract_claim
    from bharosa_ai.matching import match_person
else:
    from bharosa_ai.stubs import (  # noqa: F401
        classify_message,
        decide,
        explain,
        extract_claim,
        match_person,
        read_document,
    )

def capabilities() -> dict:
    """Which of the six functions are real, which run on an offline fallback, and why. Safe to log and show: no secret in it.
    mode per function: "stub" | "real" | "real_offline_fallback" (real code, optional helper missing) | "real_quality_only" (no OCR engine)."""
    names = ("classify_message", "match_person", "extract_claim", "read_document", "decide", "explain")
    if AI_MODE != "real":
        return {"ai_mode": AI_MODE, "functions": {n: {"mode": "stub", "why": "AI_MODE=stub: fixed realistic outputs"} for n in names}}
    from bharosa_ai import llm, ocr

    fns = {n: {"mode": "real", "why": "offline, deterministic"} for n in names}
    if llm.enabled():
        fns["extract_claim"] = {"mode": "real", "why": "offline parser + LLM assist"}
    elif llm.unavailable():
        fns["extract_claim"] = {"mode": "real_offline_fallback", "why": "%s: offline parser only, confidence -0.05, reason 'llm_unavailable'" % llm.status()}
    else:
        fns["extract_claim"] = {"mode": "real", "why": "offline parser (LLM %s)" % llm.status()}
    engine = ocr.engine_name()
    fns["read_document"] = ({"mode": "real", "why": "quality gate + OCR (%s)" % engine} if engine
                            else {"mode": "real_quality_only", "why": "no OCR engine available: quality gate only, confidence capped at 0.75"})
    return {"ai_mode": AI_MODE, "functions": fns}


def describe() -> str:
    """One readable line for the startup log."""
    caps = capabilities()
    return "AI_MODE=%s | " % caps["ai_mode"] + "; ".join("%s=%s (%s)" % (n, f["mode"], f["why"]) for n, f in caps["functions"].items())


__all__ = [
    "capabilities",
    "describe",
    "AI_MODE",
    "classify_message",
    "match_person",
    "extract_claim",
    "read_document",
    "decide",
    "explain",
]
