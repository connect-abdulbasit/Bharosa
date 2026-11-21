"""find_duplicates: records that probably describe the same person, or the same ID used by different people. Pure, offline, deterministic.

NOT one of the six contract functions (contracts/ai_interface.py has no duplicate detection), so it is not exported from
bharosa_ai/__init__.py and the backend does not call it yet; see ai/tasks/plan.md section 13.4 for the contract proposal.
Two findings, from the identity-card checklist:
- same 13-digit CNIC on records with clearly different names (one ID, two people);
- same name AND same date of birth on records with different CNICs (one person, two IDs).
Every finding carries a confidence, a plain-language reason and a model_version. Spelling variants are not duplicates of a
different person: names are compared with the same phonetic matcher as match_person.
"""
import re
from collections import defaultdict
from typing import Dict, List, Literal

from pydantic import BaseModel

from bharosa_ai.matching import MATCH_MIN, _align, _dob, _tokens
from contracts.schemas import PersonRecord

MODEL_VERSION = "dup-rules-1.0"
MAX_RECORDS = 5000  # the grouping is linear, but each group is compared pairwise: refuse absurd inputs instead of hanging


class DuplicateFinding(BaseModel):
    kind: Literal["same_cnic_different_name", "same_name_and_dob_different_cnic"]
    cnics: List[str]
    names: List[str]
    reason: str
    confidence: float
    model_version: str


def _digits(cnic: str) -> str:
    return re.sub(r"\D", "", cnic or "")


def _name_score(a: PersonRecord, b: PersonRecord) -> float:
    """Best word-alignment score between the two records' names, aliases included (0..1)."""
    best = 0.0
    for x in [a.full_name] + list(a.aliases):
        for y in [b.full_name] + list(b.aliases):
            tx, ty = _tokens(x), _tokens(y)
            if tx and ty:
                best = max(best, _align(tx, ty)[0])
    return best


def find_duplicates(records: List[PersonRecord]) -> List[DuplicateFinding]:
    findings: List[DuplicateFinding] = []
    records = list(records or [])[:MAX_RECORDS]
    by_cnic: Dict[str, List[PersonRecord]] = defaultdict(list)
    by_dob: Dict[str, List[PersonRecord]] = defaultdict(list)
    for r in records:
        if len(_digits(r.cnic)) == 13:
            by_cnic[_digits(r.cnic)].append(r)
        if _dob(r.date_of_birth):
            by_dob[_dob(r.date_of_birth)].append(r)

    for cnic in sorted(by_cnic):
        group = by_cnic[cnic]
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                score = _name_score(a, b)
                if score < MATCH_MIN:  # the same ID on records whose names do not agree
                    findings.append(DuplicateFinding(
                        kind="same_cnic_different_name", cnics=[cnic], names=[a.full_name, b.full_name], model_version=MODEL_VERSION,
                        confidence=0.9 if score < 0.5 else 0.6,
                        reason="The same ID number is on two records with different names (%s and %s): one ID, two people?" % (a.full_name, b.full_name)))

    for dob in sorted(by_dob):
        group = by_dob[dob]
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if _digits(a.cnic) == _digits(b.cnic):
                    continue  # same ID: handled above
                score = _name_score(a, b)
                if score >= MATCH_MIN:
                    findings.append(DuplicateFinding(
                        kind="same_name_and_dob_different_cnic", cnics=[a.cnic, b.cnic], names=[a.full_name, b.full_name],
                        model_version=MODEL_VERSION, confidence=0.85 if score >= 0.9 else 0.65,
                        reason="Two records have the same name and date of birth but different ID numbers: one person, two IDs?"))
    return findings
