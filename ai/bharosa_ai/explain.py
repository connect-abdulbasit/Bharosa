"""TODO(Ali): real implementation of explain. Must satisfy contracts/ai_interface.py."""
from typing import Any, Dict, List, Literal, Optional, Union  # noqa: F401

from contracts.ai_interface import (  # noqa: F401
    ClaimDraft,
    Decision,
    DocumentReading,
    Evidence,
    ExtractionError,
    MatchResult,
    MessageVerdict,
)
from contracts.schemas import PersonRecord, RuleVersion  # noqa: F401


def explain(trace: Dict[str, Any], lang: Literal["ur", "en"]) -> str:
    # TODO(Ali): implement. Return calibrated confidence + model_version. Never guess silently.
    raise NotImplementedError("TODO(Ali): explain")
