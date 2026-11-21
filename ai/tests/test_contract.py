"""Contract invariants shared by the stub and the real implementations.

Every AI output must validate against contracts/ai_interface.py, carry a confidence in 0..1 and a short
model_version (the backend column is String(40)), and no function may raise on empty or hostile input.
The "real" run skips a function that is not implemented yet (NotImplementedError).
"""
import importlib
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from bharosa_ai import stubs
from contracts.ai_interface import (
    ClaimDraft, Decision, DocumentReading, Evidence, ExtractionError, MatchResult, MessageVerdict)
from contracts.schemas import Payment, PersonRecord, RuleVersion

def _load_real():
    """Import the real modules WITHOUT clobbering the package-level functions: importing the submodules `decide` and
    `explain` rebinds `bharosa_ai.decide` / `bharosa_ai.explain` from the function to the module (stub mode)."""
    import bharosa_ai

    saved = {n: getattr(bharosa_ai, n) for n in ("decide", "explain")}
    mods = {n: importlib.import_module("bharosa_ai." + n) for n in ("classify", "matching", "extract", "document", "decide", "explain")}
    for n, f in saved.items():
        setattr(bharosa_ai, n, f)
    return mods


_M = _load_real()
IMPLS = {
    "stub": SimpleNamespace(classify_message=stubs.classify_message, match_person=stubs.match_person,
                            extract_claim=stubs.extract_claim, read_document=stubs.read_document,
                            decide=stubs.decide, explain=stubs.explain),
    "real": SimpleNamespace(classify_message=_M["classify"].classify_message, match_person=_M["matching"].match_person,
                            extract_claim=_M["extract"].extract_claim, read_document=_M["document"].read_document,
                            decide=_M["decide"].decide, explain=_M["explain"].explain),
}
RULE = RuleVersion(rule_id="r1", version=3)
CANDS = [PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", aliases=["Mohammad Aslam"]),
         PersonRecord(cnic="0000042101002", full_name="Fatima Noor")]


def _jpeg(w=640, h=400):
    out = io.BytesIO()
    Image.new("L", (w, h), 128).save(out, "JPEG")
    return out.getvalue()


def _call(impl, name, *args):
    try:
        return getattr(impl, name)(*args)
    except NotImplementedError:
        pytest.skip("%s not implemented yet" % name)


@pytest.fixture(params=["stub", "real"])
def impl(request):
    return request.param, IMPLS[request.param]


def _check_meta(kind, out):
    assert 0.0 <= out.confidence <= 1.0
    assert out.model_version and len(out.model_version) <= 40
    if kind == "real":
        assert not out.model_version.startswith("stub")


HOSTILE_TEXTS = ["", " ", "x" * 10000, "Pay fee http://bit.ly/x ​١٢", "فیس جمع کروائیں", "9O9O \x00 �"]


@pytest.mark.parametrize("text", HOSTILE_TEXTS)
@pytest.mark.parametrize("sender", ["", "9090", "9O9O", "0300-0000000", "s" * 500])
def test_classify_contract(impl, text, sender):
    kind, i = impl
    out = _call(i, "classify_message", text, sender)
    assert isinstance(out, MessageVerdict) and out.reasons is not None
    _check_meta(kind, out)


@pytest.mark.parametrize("name", ["", "   ", "Mohammad Aslam", "محمد اسلم", "x" * 5000])
@pytest.mark.parametrize("cands", [[], CANDS])
def test_match_contract(impl, name, cands):
    kind, i = impl
    out = _call(i, "match_person", name, None, cands)
    assert isinstance(out, MatchResult)
    _check_meta(kind, out)
    assert 0.0 <= out.score <= 1.0
    assert out.match_id is None or out.match_id in {c.cnic for c in cands}


@pytest.mark.parametrize("text", ["", "hi", "mujhe is mahine ke paisay nahi mile", "mujhe paisay kam mile hain",
                                  "مجھے پیسے نہیں ملے", "x" * 10000])
def test_extract_contract(impl, text):
    kind, i = impl
    out = _call(i, "extract_claim", text)
    assert isinstance(out, (ClaimDraft, ExtractionError))
    _check_meta(kind, out)


@pytest.mark.parametrize("data", [b"", b"garbage", b"x" * 500, _jpeg()])
def test_document_contract(impl, data):
    kind, i = impl
    out = _call(i, "read_document", data)
    assert isinstance(out, DocumentReading)
    _check_meta(kind, out)
    assert 0.0 <= out.blur_score <= 1.0 and all(isinstance(v, str) for v in out.fields.values())


def _claim(conf):
    return ClaimDraft(claimant_name="Muhammad Aslam", claim_type="missing", confidence=conf, model_version="t")


EVIDENCE = [Evidence(), Evidence(red_flags=["short_payment"]), Evidence(payment_step=True),
            Evidence(mock_failures=["identity"]),
            Evidence(match=MatchResult(match_id=None, score=0.1, confidence=0.4, model_version="t")),
            Evidence(ledger=[Payment(payment_id="p", amount_pkr=8000, date="2026-10-05", agent_id="a")])]


@pytest.mark.parametrize("conf", [0.0, 0.5, 0.75, 0.95, 1.0])
@pytest.mark.parametrize("ev", EVIDENCE)
def test_decide_contract(impl, conf, ev):
    kind, i = impl
    out = _call(i, "decide", _claim(conf), ev, RULE)
    assert isinstance(out, Decision) and out.rule_version == RULE.version and out.reasons
    _check_meta(kind, out)
    json.dumps(out.trace)  # the trace is stored in a JSON column


TRACES = [{}, {"action": "ask_more"}, {"action": "send_to_human", "flags": ["short_payment"], "shortfall": 4000},
          {"action": "auto_handle", "payment_needed": True}, {"action": "bogus"}, {"action": None},
          {"terminal": True, "failed_step": "identity_lookup", "action": "send_to_human"}]


@pytest.mark.parametrize("trace", TRACES)
@pytest.mark.parametrize("lang", ["ur", "en", "fr"])
def test_explain_contract(impl, trace, lang):
    _, i = impl
    out = _call(i, "explain", trace, lang)
    assert isinstance(out, str) and out.strip()
