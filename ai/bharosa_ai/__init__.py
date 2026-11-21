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

__all__ = [
    "AI_MODE",
    "classify_message",
    "match_person",
    "extract_claim",
    "read_document",
    "decide",
    "explain",
]
