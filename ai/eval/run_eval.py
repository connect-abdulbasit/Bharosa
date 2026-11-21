"""Offline evaluation of the real AI functions on the synthetic cases in ai/data/. Writes ai/eval/eval_results.json
(the exact path the backend reads for GET /eval `model_eval`), shaped like contracts.schemas.EvalResults plus extra keys.

Run:  python ai/eval/run_eval.py [--split all|test|val|train] [--out PATH] [--no-images]
(default `all`: the case sets are small, so the 20% test split alone has too few cases to mean anything.)

HONESTY: the data is synthetic and written by the author of the rules, so these numbers are an UPPER BOUND, not a
forecast. The decision section scores the rule implementation against an ideal action defined by the written policy,
under noisy component confidences; it does not measure real-world accuracy. Cost model: wrong approval 10, wrong
rejection 5, human review 1.
"""
import argparse
import datetime
import importlib.util
import json
import os
import random
import statistics
import sys
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Tuple

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
for _p in (str(AI_DIR.parent), str(AI_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from bharosa_ai import llm, ocr  # noqa: E402
from bharosa_ai.classify import classify_message  # noqa: E402
from bharosa_ai.decide import decide  # noqa: E402
from bharosa_ai.document import read_document  # noqa: E402
from bharosa_ai.explain import explain  # noqa: E402
from bharosa_ai.extract import extract_claim  # noqa: E402
from bharosa_ai.matching import match_person  # noqa: E402
from contracts.ai_interface import ClaimDraft, DocumentReading, Evidence, ExtractionError, MatchResult  # noqa: E402
from contracts.enums import DecisionAction  # noqa: E402
from contracts.schemas import EvalResults, Payment, PersonRecord, RuleVersion  # noqa: E402

COSTS = {"wrong_approval": 10, "wrong_rejection": 5, "human_review": 1}
AUTO, ASK, HUMAN = DecisionAction.auto_handle, DecisionAction.ask_more, DecisionAction.send_to_human
RULE = RuleVersion(rule_id="eval-rule", version=1)
OUT_PATH = HERE / "eval_results.json"


def _load(name: str):
    spec = importlib.util.spec_from_file_location("eval_" + name, AI_DIR / "data" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CASES = _load("cases")


def _pick(items: List[tuple], prefix: str, split: str) -> List[tuple]:
    return [it for i, it in enumerate(items) if split == "all" or CASES.split_of("%s-%d" % (prefix, i)) == split]


def _ece(pairs: List[Tuple[float, bool]], bins: int = 10) -> Tuple[float, List[Dict[str, Any]]]:
    """Expected calibration error and the reliability table: do 'confidence 0.9' answers turn out right 90% of the time?"""
    total, err, table = len(pairs), 0.0, []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        members = [(c, ok) for c, ok in pairs if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if members:
            conf, acc = sum(c for c, _ in members) / len(members), sum(ok for _, ok in members) / len(members)
            err += len(members) / total * abs(acc - conf)
            table.append({"bin": "%.1f-%.1f" % (lo, hi), "n": len(members), "confidence": round(conf, 3), "accuracy": round(acc, 3)})
    return (round(err, 4) if total else 0.0), table


def _ratio(num: float, den: float, empty: Any = 0.0) -> Any:
    """num / den, or `empty` when there are no cases (0 of 0 must not read as a score)."""
    return round(num / den, 4) if den else empty


def eval_classifier(split: str) -> Dict[str, Any]:
    rows = _pick(CASES.MESSAGES, "msg", split)
    confusion: Dict[str, Counter] = {g: Counter() for g in ("scam", "genuine", "unsure")}
    pairs, by_lang, hard_miss = [], {}, 0
    for text, sender, gold, lang, hard in rows:
        v = classify_message(text, sender)
        pred = v.label.value
        confusion[gold][pred] += 1
        pairs.append((v.confidence, pred == gold))
        by_lang.setdefault(lang, []).append(pred == gold)
        hard_miss += 1 if (hard and pred != gold) else 0
    n = len(rows)
    tp, pred_scam = confusion["scam"]["scam"], sum(c["scam"] for c in confusion.values())
    dangerous = confusion["scam"]["genuine"] + confusion["genuine"]["scam"]
    ece, table = _ece(pairs)
    metrics = {"accuracy": _ratio(sum(ok for _, ok in pairs), n), "precision_scam": _ratio(tp, pred_scam),
               "recall_scam": _ratio(tp, sum(confusion["scam"].values())), "unsure_rate": _ratio(sum(c["unsure"] for c in confusion.values()), n),
               "dangerous_error_rate": _ratio(dangerous, n), "ece": ece, "n": float(n)}
    genuine_n, scam_n = sum(confusion["genuine"].values()), sum(confusion["scam"].values())
    metrics.update({  # the numbers the judges ask for, under their own names
        "false_alarm_rate": _ratio(confusion["genuine"]["scam"], genuine_n),          # real notices called scam (people blocked)
        "genuine_to_unsure_rate": _ratio(confusion["genuine"]["unsure"], genuine_n),  # real notices that only get a "not sure"
        "missed_scam_rate": _ratio(scam_n - tp, scam_n),                              # scams not called scam
        "missed_scam_as_unsure": float(confusion["scam"]["unsure"]), "missed_scam_as_genuine": float(confusion["scam"]["genuine"])})
    metrics.update({"accuracy_" + lang: _ratio(sum(v), len(v)) for lang, v in sorted(by_lang.items())})
    return {"metrics": metrics, "confusion": {g: dict(c) for g, c in confusion.items()}, "reliability": table, "hard_cases_missed": hard_miss}


def eval_matching(split: str) -> Dict[str, Any]:
    rows = _pick(CASES.NAMES, "name", split)
    correct = false_match = missed = 0
    pairs, kinds = [], Counter()
    for query, names, expected, kind, hard in rows:
        people = [PersonRecord(cnic="0000042101%03d" % i, full_name=n) for i, n in enumerate(names)]
        want = people[expected].cnic if expected is not None else None
        got = match_person(query, None, people)
        ok = got.match_id == want
        correct += ok
        false_match += 1 if (got.match_id is not None and not ok) else 0
        missed += 1 if (want is not None and got.match_id is None) else 0
        if got.match_id is not None:
            pairs.append((got.confidence, ok))
        if not ok:
            kinds[kind] += 1
    n = len(rows)
    ece, table = _ece(pairs)
    return {"metrics": {"top1_accuracy": _ratio(correct, n), "false_match_rate": _ratio(false_match, n), "miss_rate": _ratio(missed, n),
                        "ece": ece, "n": float(n)}, "reliability": table, "errors_by_kind": dict(kinds)}


def eval_extraction(split: str) -> Dict[str, Any]:
    return _score_transcripts(_pick(CASES.TRANSCRIPTS, "tr", split))


def _score_transcripts(rows: List[tuple]) -> Dict[str, Any]:
    ok_rows = [(t, e) for t, e in rows if "error" not in e]
    bad_rows = [(t, e) for t, e in rows if "error" in e]
    understood = type_ok = name_ok = period_n = period_ok = amount_n = amount_ok = 0
    for text, exp in ok_rows:
        out = extract_claim(text)
        if not isinstance(out, ClaimDraft):
            continue
        understood += 1
        type_ok += out.claim_type == exp["type"]
        name_ok += out.claimant_name.casefold() == exp["name"].casefold()
        if "period" in exp:
            period_n, period_ok = period_n + 1, period_ok + (out.period == exp["period"])
        if "amount" in exp:
            amount_n, amount_ok = amount_n + 1, amount_ok + (out.amount_claimed_pkr == exp["amount"])
    refused = right_code = invented = 0
    for text, exp in bad_rows:
        out = extract_claim(text)
        if isinstance(out, ExtractionError):
            refused += 1
            right_code += out.error == exp["error"]
        else:
            invented += 1
    return {"understood_rate": _ratio(understood, len(ok_rows), None), "claim_type_accuracy": _ratio(type_ok, understood, None),
            "name_accuracy": _ratio(name_ok, understood, None), "period_accuracy": _ratio(period_ok, period_n, None),
            "amount_accuracy": _ratio(amount_ok, amount_n, None), "refusal_rate": _ratio(refused, len(bad_rows), None),
            "refusal_reason_accuracy": _ratio(right_code, len(bad_rows), None), "invented_claim_rate": _ratio(invented, len(bad_rows), None),
            "n": float(len(rows))}


@contextmanager
def _env(**changes: str):
    """Set environment variables for a block and put them back."""
    saved = {k: os.environ.get(k) for k in changes}
    os.environ.update(changes)
    try:
        yield
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def eval_documents() -> Dict[str, float]:
    with _env(AI_USE_OCR="0"):  # this is the blur gate only; OCR has its own block
        return _eval_documents()


def eval_document_ocr(limit: int = 4) -> Any:
    """OCR on generated fake CNIC cards (sharp and slightly soft): exact-match rates for CNIC, name, father's name and date of birth, and
    the time per photo. None when no OCR engine is installed. Synthetic cards only (no real CNIC images are allowed), so this says the
    pipeline works, NOT how well it reads real phone photos."""
    with _env(AI_USE_OCR=os.environ.get("AI_USE_OCR", "1")):
        if not ocr.available():
            return None
        maker = _load("make_images").make_cnic_card
        people = [("Muhammad Aslam", "Abdul Rehman", "00000-4210100-1", "12.03.1984", "M"), ("Fatima Noor", "Noor Muhammad", "00000-4210100-2", "01.07.1979", "F"),
                  ("Gul Bano", "Mir Hassan", "00000-4210100-3", "30.01.1990", "F"), ("Zubaida Khatoon", "Ghulam Hussain", "00000-4210100-4", "23.11.1968", "F")][:limit]
        hits: Dict[str, List[bool]] = {"cnic": [], "name": [], "father_name": [], "date_of_birth": [], "format_ok": []}
        times, confidences = [], []
        for seed, (name, father, cnic, dob, gender) in enumerate(people, 1):
            for blur in (0.0, 1.5):
                start = time.perf_counter()
                r = read_document(maker(seed, name=name, father=father, cnic=cnic, dob=dob, gender=gender, blur=blur))
                times.append((time.perf_counter() - start) * 1000)
                confidences.append(r.confidence)
                day, month, year = dob.split(".")
                hits["cnic"].append(r.fields.get("cnic") == cnic.replace("-", ""))
                hits["name"].append(r.fields.get("name", "").casefold() == name.casefold())
                hits["father_name"].append(r.fields.get("father_name", "").casefold() == father.casefold())
                hits["date_of_birth"].append(r.fields.get("date_of_birth") == "%s-%s-%s" % (year, month, day))
                hits["format_ok"].append(r.format_ok)
        n = len(times)
        return {"engine": ocr.engine_name(), "n": n, "cnic_exact": _ratio(sum(hits["cnic"]), n), "name_exact": _ratio(sum(hits["name"]), n),
                "father_name_exact": _ratio(sum(hits["father_name"]), n), "date_of_birth_exact": _ratio(sum(hits["date_of_birth"]), n),
                "format_ok_rate": _ratio(sum(hits["format_ok"]), n), "average_confidence": round(sum(confidences) / n, 3),
                "median_ms_per_photo": round(statistics.median(times), 1),
                "note": "synthetic fake cards only (sharp and slightly soft); real phone photos will read worse"}


def _eval_documents() -> Dict[str, float]:
    """Blur gate on generated fake cards. Blur is judged relative to the image width; the grey zone between is not scored."""
    maker = _load("make_images").make_card
    usable, retake = [], []
    for seed in (1, 2):
        for width in (1024, 1600):
            for per_1000 in (0.0, 0.5, 1.0, 1.5):
                usable.append(read_document(maker(seed, width, int(width * 0.63), blur=per_1000 * width / 1000)).blur_score <= 0.5)
            for per_1000 in (2.7, 3.5, 5.0, 7.0):
                retake.append(read_document(maker(seed, width, int(width * 0.63), blur=per_1000 * width / 1000)).blur_score > 0.5)
        for kwargs in ({"brightness": 0.15}, {"contrast": 0.2}, {"brightness": 3.0}):
            retake.append(read_document(maker(seed, **kwargs)).blur_score > 0.5)
    return {"good_photos_accepted": _ratio(sum(usable), len(usable)), "bad_photos_sent_for_retake": _ratio(sum(retake), len(retake)),
            "n": float(len(usable) + len(retake))}


def eval_classifier_cv() -> Any:
    """Rules versus rules + text model (TF-IDF + logistic regression + calibration), 5-fold cross-validated, from eval/compare_ml.py.
    None when scikit-learn is not installed (it is a dev-only extra)."""
    try:
        spec = importlib.util.spec_from_file_location("compare_ml_for_eval", HERE / "compare_ml.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.compare()
    except ImportError:
        return None


RULE_FLAGS = ["short_payment", "duplicate_payment", "lookalike_sender", "mock_service_failure", "claim_contradicts_ledger"]
SCENARIO_RULE = RuleVersion(rule_id="scenario-rule", version=1, red_flags=RULE_FLAGS)
PROGRAMME_AMOUNT = 12000


def _scenario_action(c: Dict[str, Any]) -> str:
    """One scenario through the real extract_claim -> match_person -> decide. The ledger flags and the payment-check overrides are a
    copy of backend/app/services/pipeline.py (step_ledger_lookup, step_decide), so a change there must be mirrored here."""
    check = c["kind"] == "payment_check"
    if check:
        draft = ClaimDraft(claimant_name=c["account"], claim_type="payment_check", period="2026-10", confidence=1.0, model_version="structured-input")
    else:
        extracted = extract_claim(c["transcript"])
        if isinstance(extracted, ExtractionError):
            return ASK.value  # the pipeline stops here: Terminal("ask_more")
        draft = extracted
    unique, seen, found = [], set(), []
    for amount in c["payments"]:
        key = ("2026-10-05", amount, "agent-017")
        if key in seen:
            if "duplicate_payment" not in found:
                found.append("duplicate_payment")
            continue
        seen.add(key)
        unique.append(Payment(payment_id="p%d" % len(unique), amount_pkr=amount, date="2026-10-05", agent_id="agent-017"))
    received = sum(p.amount_pkr for p in unique)
    if 0 < received < PROGRAMME_AMOUNT:
        found.append("short_payment")
    if not check and (received >= PROGRAMME_AMOUNT or (received == 0 and draft.claim_type == "short_paid")):
        found.append("claim_contradicts_ledger")
    payment_needed = (not check) and PROGRAMME_AMOUNT - received > 0 and "claim_contradicts_ledger" not in found
    person = PersonRecord(cnic="0000042101001", full_name=c["identity"], aliases=c["aliases"])
    document = (DocumentReading(fields={}, blur_score=0.1, format_ok=True, confidence=0.75, model_version="eval")
                if c["photo"] == "clear" else None)
    evidence = Evidence(match=match_person(draft.claimant_name, None, [person]), document=document, ledger=unique,
                        red_flags=[f for f in found if f in SCENARIO_RULE.red_flags], payment_step=payment_needed,
                        mock_failures=["identity_lookup"] if c["mock_failure"] else [])
    action = decide(draft, evidence, SCENARIO_RULE).action.value
    if check:  # only a CONFIRMED full payment may be auto-handled; anything else is routed, never guessed
        if ("duplicate_payment" in found or 0 < received < PROGRAMME_AMOUNT) and action != HUMAN.value:
            action = HUMAN.value
        elif received == 0 and action == AUTO.value:
            action = ASK.value
    return action


def eval_scenarios() -> Dict[str, Any]:
    """The fifty labelled end-to-end cases (data/decision_cases.py) scored with the 10 / 5 / 1 costs."""
    cases = _load("decision_cases").CASES
    results = [(c, _scenario_action(c)) for c in cases]
    pairs = [(next(a for a in (AUTO, ASK, HUMAN) if a.value == c["expected"]), next(a for a in (AUTO, ASK, HUMAN) if a.value == got))
             for c, got in results]
    counts = _counts(pairs)
    spoken = [got for c, got in results if c["kind"] == "claim"]
    confusion: Dict[str, Dict[str, int]] = {}
    for c, got in results:
        confusion.setdefault(c["expected"], {}).setdefault(got, 0)
        confusion[c["expected"]][got] += 1
    return {"n": len(cases), "accuracy": _ratio(sum(1 for c, got in results if got == c["expected"]), len(cases)),
            "wrong_approvals": counts["wrong_approvals"], "wrong_rejections": counts["wrong_rejections"], "human_reviews": counts["human_reviews"],
            "total_cost": counts["total_cost"], "spoken_claims": len(spoken), "spoken_claims_auto_handled": sum(1 for a in spoken if a == AUTO.value),
            "by_kind": {k: _ratio(sum(1 for c, got in results if c["kind"] == k and got == c["expected"]), sum(1 for c, _ in results if c["kind"] == k))
                        for k in ("claim", "payment_check")},
            "confusion": confusion,
            "mismatches": [{"id": c["id"], "expected": c["expected"], "got": got, "note": c["note"]} for c, got in results if got != c["expected"]],
            "note": "labels are written by the rule author from the written policy; flags are computed like backend/app/services/pipeline.py"}


def eval_llm_comparison() -> Dict[str, Any]:
    """Offline parser versus LLM-assisted extraction on natural wording. Needs the LLM to be on; the default run never calls it.
    Records only scores and the LLM status, never any reply text."""
    rows = list(CASES.NATURAL_TRANSCRIPTS)
    previous = os.environ.get("AI_USE_LLM")
    os.environ["AI_USE_LLM"] = "0"
    try:
        offline = _score_transcripts(rows)
    finally:
        if previous is None:
            os.environ.pop("AI_USE_LLM", None)
        else:
            os.environ["AI_USE_LLM"] = previous
    llm.reset_stats()
    assisted = _score_transcripts(rows)
    return {"llm_status": llm.status(), "n": len(rows), "offline": offline, "llm_assisted": assisted,
            "llm_cost": _llm_cost_block(llm.stats(), len(rows))}


def _load_dotenv(path: Path) -> None:
    """Script-only convenience for local runs: put KEY=VALUE lines of ai/.env into the environment. Never prints a value."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _counts(pairs: List[Tuple[Any, Any]]) -> Dict[str, int]:
    wa = sum(1 for ideal, act in pairs if act == AUTO and ideal != AUTO)
    wr = sum(1 for ideal, act in pairs if act != AUTO and ideal == AUTO)
    hr = sum(1 for _, act in pairs if act == HUMAN)
    return {"auto_handle": sum(1 for _, a in pairs if a == AUTO), "ask_more": sum(1 for _, a in pairs if a == ASK), "send_to_human": hr,
            "wrong_approvals": wa, "wrong_rejections": wr, "human_reviews": hr,
            "under_escalations": sum(1 for ideal, act in pairs if act == ASK and ideal == HUMAN),
            "total_cost": COSTS["wrong_approval"] * wa + COSTS["wrong_rejection"] * wr + COSTS["human_review"] * hr}


def _by_threshold(value: float) -> DecisionAction:
    return AUTO if value >= RULE.auto_handle_min else ASK if value >= RULE.ask_more_min else HUMAN


def eval_decision(n: int = 1000, seed: int = 2026, noise: float = 0.02) -> Dict[str, Any]:
    """Ideal action by construction: clean -> auto_handle, weak proof -> ask_more, red flag / no name match / low confidence -> human.
    Component confidences get Gaussian noise, so a good result needs a margin, not luck."""
    rng = random.Random(seed)
    flags_pool = ["short_payment", "duplicate_payment", "claim_contradicts_ledger", "lookalike_sender"]
    ours, naive_claim, naive_avg, always = [], [], [], []
    for _ in range(n):
        kind = rng.choices(["clean", "weak", "flag", "noname", "low"], [35, 25, 20, 8, 12])[0]
        comps = [rng.uniform(0.92, 1.0) for _ in range(3)]
        flags, matched, ideal = [], True, AUTO
        if kind == "weak":
            comps[rng.randrange(3)], ideal = rng.uniform(0.62, 0.86), ASK
        elif kind == "flag":
            flags, ideal = [rng.choice(flags_pool)], HUMAN
        elif kind == "noname":
            comps[1], matched, ideal = rng.uniform(0.3, 0.5), False, HUMAN
        elif kind == "low":
            comps[rng.randrange(3)], ideal = rng.uniform(0.1, 0.55), HUMAN
        seen = [min(max(c + rng.gauss(0, noise), 0.0), 1.0) for c in comps]
        claim = ClaimDraft(claimant_name="Eval Person", claim_type="missing", confidence=seen[0], model_version="eval")
        ev = Evidence(match=MatchResult(match_id="0000042101001" if matched else None, score=seen[1], confidence=seen[1], model_version="eval"),
                      document=DocumentReading(fields={}, blur_score=0.1, format_ok=True, confidence=seen[2], model_version="eval"),
                      red_flags=flags)
        ours.append((ideal, decide(claim, ev, RULE).action))
        naive_claim.append((ideal, _by_threshold(seen[0])))
        naive_avg.append((ideal, _by_threshold(sum(seen) / 3)))
        always.append((ideal, HUMAN))
    result: Dict[str, Any] = dict(_counts(ours), n=n, noise=noise, ideal_counts={k.value: sum(1 for i, _ in ours if i == k) for k in (AUTO, ASK, HUMAN)})
    result["baselines"] = {"claim_confidence_only": _counts(naive_claim), "average_confidence_no_stops": _counts(naive_avg), "always_send_to_human": _counts(always)}
    return result


def eval_latency(images: bool = True) -> Dict[str, float]:
    """Median milliseconds per call of every real function, on fixed inputs (offline, LLM off)."""
    people = [PersonRecord(cnic="0000042101001", full_name="Muhammad Aslam", aliases=["Mohammad Aslam"])]
    claim = ClaimDraft(claimant_name="Muhammad Aslam", claim_type="missing", confidence=0.8, model_version="eval")
    trace = {"action": "ask_more", "needs": ["A clear photo of your ID card"], "flags": ["short_payment"], "shortfall": 4000}
    calls = {"classify_message": (lambda: classify_message("Pay fee at http://bit.ly/x to get relief", "SAHARA-INFO"), 200),
             "match_person": (lambda: match_person("Mohammad Aslam", None, people), 200),
             "extract_claim": (lambda: extract_claim("Mera naam Gul Bano hai, is mahine paisay nahi mile"), 200),
             "decide": (lambda: decide(claim, Evidence(), RULE), 200),
             "explain": (lambda: explain(trace, "ur"), 200)}
    if images:
        card = _load("make_images").make_card(1)

        def quality_only():
            with _env(AI_USE_OCR="0"):
                return read_document(card)

        calls["read_document"] = (quality_only, 10)  # the quality gate alone; OCR is timed below
    out = {}
    for name, (fn, repeats) in calls.items():
        times = []
        for _ in range(repeats):
            start = time.perf_counter()
            fn()
            times.append((time.perf_counter() - start) * 1000)
        out[name] = round(statistics.median(times), 3)
    if images:
        with _env(AI_USE_OCR=os.environ.get("AI_USE_OCR", "1")):
            if ocr.available():  # reading the card text is far slower than the quality gate: time it separately
                cnic_card, times = _load("make_images").make_cnic_card(1), []
                for _ in range(2):
                    start = time.perf_counter()
                    read_document(cnic_card)
                    times.append((time.perf_counter() - start) * 1000)
                out["read_document_ocr"] = round(statistics.median(times), 1)
    return out


def _llm_cost_block(usage: Dict[str, int], cases: int) -> Dict[str, Any]:
    """LLM calls, tokens and (only when LLM_PRICE_PER_1M_TOKENS is set) money per case. Never contains a secret."""
    try:
        price = float(os.environ.get("LLM_PRICE_PER_1M_TOKENS", ""))
    except ValueError:
        price = 0.0
    tokens = usage.get("tokens", 0)
    return {"llm": "on", "calls": usage.get("calls", 0), "ok_calls": usage.get("ok", 0), "tokens": tokens, "cases": cases,
            "calls_per_case": round(usage.get("calls", 0) / cases, 3) if cases else None,
            "tokens_per_call": round(tokens / usage["ok"], 1) if usage.get("ok") and tokens else None,
            "cost_per_case_usd": round(tokens / 1e6 * price / cases, 6) if price and tokens and cases else None}


CHART_PATH = HERE / "cost_chart.png"
GRID = 2000  # confidence grid for the cost curves: deterministic, no sampling noise


def eval_cost_curves(cases: int = 1000) -> Dict[str, Any]:
    """Cost per threshold under the given costs, for a CALIBRATED population: confidence is spread evenly over 0..1 and a case with
    confidence c is truly legitimate with probability c. Priced: auto-approve costs 10 when the case was not legitimate (wrong
    approval); sending to a person costs 1 (human review); auto-rejecting would cost 5 when the case was legitimate (wrong
    rejection). The best upper threshold then comes out at 0.90 by arithmetic ((1 - c) * 10 = 1). The lower 0.60 line (ask the
    citizen or send to an officer) is NOT priced by these costs, so its sweep is flat and marked unpriced."""
    cs = [(k + 0.5) / GRID for k in range(GRID)]
    wa_cost, rj_cost, hr_cost = COSTS["wrong_approval"], COSTS["wrong_rejection"], COSTS["human_review"]

    def upper(t: float) -> Dict[str, Any]:
        wrong = sum(1 - c for c in cs if c >= t) / GRID * cases
        reviews = sum(1 for c in cs if c < t) / GRID * cases
        return {"threshold": round(t, 2), "wrong_approvals": round(wrong, 2), "human_reviews": round(reviews, 2),
                "total_cost": round(wa_cost * wrong + hr_cost * reviews, 2)}

    sweep = [upper(0.50 + i * 0.01) for i in range(51)]
    best = min(sweep, key=lambda r: r["total_cost"])
    chosen = next(r for r in sweep if r["threshold"] == 0.9)
    return {
        "assumption": "calibrated population: confidence uniform on 0..1, a case with confidence c is legitimate with probability c; "
                      "costs wrong approval 10, wrong rejection 5, human review 1 (asking the citizen is priced like a review)",
        "cases": cases, "auto_handle_min": sweep, "best_auto_handle_min": best["threshold"], "best_cost": best["total_cost"],
        "chosen_auto_handle_min": 0.9, "chosen_cost": chosen["total_cost"],
        "chosen_is_cheapest": chosen["total_cost"] <= best["total_cost"] + 1e-9,
        "ask_more_min": [{"threshold": round(0.30 + i * 0.05, 2), "total_cost": chosen["total_cost"], "priced": False} for i in range(11)],
        "ask_more_min_note": "the costs do not distinguish asking the citizen from sending to an officer, so this line cannot be proven by cost",
        "breakeven": {"approve_vs_human": round(1 - hr_cost / wa_cost, 2), "reject_vs_human": round(hr_cost / rj_cost, 2)},
        "expected_cost_by_confidence": [{"confidence": round(i / 20, 2), "approve": round(wa_cost * (1 - i / 20), 3), "human_review": float(hr_cost),
                                         "reject": round(rj_cost * i / 20, 3)} for i in range(21)],
    }


def draw_cost_chart(curves: Dict[str, Any], path: Path) -> None:
    """Two panels drawn with Pillow (no plotting dependency): total cost versus the auto-approve threshold, and the expected cost
    of each action versus confidence with the break-even points."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1400, 1180
    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    try:
        font, small, big = (ImageFont.load_default(size=s) for s in (20, 17, 28))
    except TypeError:  # Pillow older than 10.1
        font = small = big = ImageFont.load_default()

    def panel(box, series, xs, ymax, title, xlabel, ylabel, marks):
        x0, y0, x1, y1 = box
        xmin, xmax = xs
        px = lambda x: x0 + (x - xmin) / (xmax - xmin) * (x1 - x0)  # noqa: E731
        py = lambda y: y1 - min(y, ymax) / ymax * (y1 - y0)  # noqa: E731
        d.text((x0, y0 - 52), title, fill="black", font=big)
        d.rectangle(box, outline="black", width=2)
        for i in range(6):
            gy = y0 + i * (y1 - y0) / 5
            d.line([(x0, gy), (x1, gy)], fill=(225, 225, 225))
            d.text((x0 - 62, gy - 10), "%g" % round(ymax * (5 - i) / 5, 1), fill="black", font=small)
            gx = x0 + i * (x1 - x0) / 5
            d.text((gx - 20, y1 + 8), "%.2f" % (xmin + (xmax - xmin) * i / 5), fill="black", font=small)
        d.text((x0 + (x1 - x0) / 2 - 80, y1 + 36), xlabel, fill="black", font=font)
        d.text((x0 - 62, y0 - 24), ylabel, fill="black", font=small)
        for k, (label, color, pts) in enumerate(series):
            d.line([(px(x), py(y)) for x, y in pts], fill=color, width=4)
            d.line([(x1 - 330, y0 + 22 + k * 26), (x1 - 290, y0 + 22 + k * 26)], fill=color, width=4)
            d.text((x1 - 280, y0 + 12 + k * 26), label, fill="black", font=small)
        for x, text, color, row in marks:
            d.line([(px(x), y0), (px(x), y1)], fill=color, width=2)
            tx = px(x) + 6
            if tx + d.textlength(text, font=small) > x1 - 4:  # no room on the right: write the label to the left of the line
                tx = px(x) - 6 - d.textlength(text, font=small)
            d.text((tx, y0 + 8 + row * 24 + 90), text, fill=color, font=small)

    sweep = curves["auto_handle_min"]
    top = max(r["total_cost"] for r in sweep)
    series_a = [("total cost", (31, 78, 160), [(r["threshold"], r["total_cost"]) for r in sweep]),
                ("wrong approvals x 10", (200, 40, 40), [(r["threshold"], 10 * r["wrong_approvals"]) for r in sweep]),
                ("human reviews x 1", (40, 150, 70), [(r["threshold"], r["human_reviews"]) for r in sweep])]
    marks_a = [(curves["chosen_auto_handle_min"], "chosen %.2f: cost %.0f per %d cases" % (curves["chosen_auto_handle_min"], curves["chosen_cost"], curves["cases"]), (31, 78, 160), 0)]
    if curves["best_auto_handle_min"] != curves["chosen_auto_handle_min"]:
        marks_a.append((curves["best_auto_handle_min"], "cheapest %.2f: cost %.0f" % (curves["best_auto_handle_min"], curves["best_cost"]), (200, 40, 40), 1))
    panel((110, 90, 1340, 520), series_a, (0.5, 1.0), -(-top * 1.1 // 500) * 500, "1. Total cost per 1000 cases versus the auto-approve threshold",
          "auto-approve threshold (confidence at or above this is handled by the system)", "cost", marks_a)

    by_conf = curves["expected_cost_by_confidence"]
    series_b = [("auto-approve: 10 x (1 - confidence)", (200, 40, 40), [(r["confidence"], r["approve"]) for r in by_conf]),
                ("send to a person: 1", (40, 150, 70), [(r["confidence"], r["human_review"]) for r in by_conf]),
                ("auto-reject: 5 x confidence", (225, 130, 20), [(r["confidence"], r["reject"]) for r in by_conf])]
    be = curves["breakeven"]
    marks_b = [(be["reject_vs_human"], "%.2f: rejecting costs more than a person above this" % be["reject_vs_human"], (225, 130, 20), 0),
               (0.6, "0.60: ask citizen vs officer (same cost: not priced)", (90, 90, 90), 1),
               (be["approve_vs_human"], "%.2f: approving costs less than a person above this" % be["approve_vs_human"], (200, 40, 40), 2)]
    panel((110, 680, 1340, 1030), series_b, (0.0, 1.0), 10.0, "2. Expected cost of each action versus confidence",
          "confidence that the case is legitimate", "expected cost per case", marks_b)
    d.text((110, 1100), "Assumption: calibrated confidence (a case with confidence c is legitimate with probability c). "
           "Costs: wrong approval 10, wrong rejection 5, human review 1.", fill=(70, 70, 70), font=small)
    d.text((110, 1126), "Synthetic evaluation, upper bound: the 0.60 line is a service choice that this cost model cannot price.", fill=(70, 70, 70), font=small)
    img.save(path, "PNG")


def run_eval(split: str = "all", images: bool = True, compare_llm: bool = False) -> Dict[str, Any]:
    """The default run is OFFLINE (AI_USE_LLM forced to 0, so it never touches the network or a key) and reproducible.
    compare_llm=True adds an offline-versus-LLM comparison and needs a working LLM configuration."""
    saved = {k: os.environ.get(k) for k in ("AI_DEFAULT_PERIOD", "AI_USE_LLM", "AI_USE_ML")}
    os.environ["AI_DEFAULT_PERIOD"] = "2026-10"  # month words in the transcripts resolve against this, so results are reproducible
    os.environ["AI_USE_LLM"] = "0"
    os.environ["AI_USE_ML"] = "0"  # the classifier is scored as RULES only: the shipped text model has seen these messages (see classifier_cv)
    try:
        result = _run_eval(split, images)
        if compare_llm:
            os.environ["AI_USE_LLM"] = saved["AI_USE_LLM"] if saved["AI_USE_LLM"] not in (None, "0") else "1"
            result["extraction_llm"] = eval_llm_comparison()
            result["llm_cost"] = result["extraction_llm"]["llm_cost"]
        return result
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run_eval(split: str, images: bool) -> Dict[str, Any]:
    clf, mat, dec = eval_classifier(split), eval_matching(split), eval_decision()
    result: Dict[str, Any] = {
        "model_version": "ai-real-1.0", "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "classifier": clf["metrics"], "matching": mat["metrics"],
        "decision": dict(dec),
        "cost_assumptions": dict(COSTS), "total_cost": dec["total_cost"], "confusion": clf["confusion"],
        "split": split,
        "extraction": eval_extraction(split),
        "reliability": {"classifier": clf["reliability"], "matching": mat["reliability"]},
        "matching_errors_by_kind": mat["errors_by_kind"], "classifier_hard_cases_missed": clf["hard_cases_missed"],
        "notes": ["Synthetic data written by the author of the rules: scores are an upper bound, not a forecast.",
                  "decision: ideal action is defined by the written policy and component confidences carry Gaussian noise; "
                  "it checks the rule implementation and the cost trade-off, not real-world accuracy.",
                  "claim confidence from the offline parser is capped at 0.80 and photo confidence at 0.75, so a claim never auto-handles; "
                  "only structured inputs (confidence 1.0, such as a payment check) can.",
                  "The case sets are small, and rules were corrected after inspecting errors on ALL splits, so the test split is not a clean "
                  "hold-out: treat every number as optimistic."],
    }
    if images:
        result["document"] = eval_documents()
        result["document_ocr"] = eval_document_ocr()
    result["cost_curve"] = eval_cost_curves()
    result["classifier_cv"] = eval_classifier_cv()
    result["scenarios"] = eval_scenarios()
    result["latency_ms"] = eval_latency(images)
    result["llm_cost"] = {"llm": "off", "calls_per_case": 0.0, "cost_per_case_usd": None,
                          "note": "the default evaluation is offline; run with --llm to measure calls, tokens and cost per case"}
    EvalResults(**result)  # fails loudly if the shape ever drifts from the contract
    return result


def _print(r: Dict[str, Any]) -> None:
    c, m, d, e = r["classifier"], r["matching"], r["decision"], r["extraction"]
    print("split=%s  (synthetic data: upper bound)" % r["split"])
    print("classifier  n=%d  accuracy %.3f  precision_scam %.3f  recall_scam %.3f  dangerous %.3f  ece %.3f" % (
        c["n"], c["accuracy"], c["precision_scam"], c["recall_scam"], c["dangerous_error_rate"], c["ece"]))
    print("matching    n=%d  top1 %.3f  false_match %.3f  miss %.3f  ece %.3f" % (m["n"], m["top1_accuracy"], m["false_match_rate"], m["miss_rate"], m["ece"]))
    shown = {k: ("n/a" if v is None else "%.3f" % v) for k, v in e.items() if k != "n"}
    print("extraction  n=%d  understood %s  type %s  name %s  refusal %s  INVENTED %s" % (
        e["n"], shown["understood_rate"], shown["claim_type_accuracy"], shown["name_accuracy"], shown["refusal_rate"], shown["invented_claim_rate"]))
    if "document" in r:
        print("document    n=%d  good accepted %.3f  bad sent for retake %.3f" % (r["document"]["n"], r["document"]["good_photos_accepted"], r["document"]["bad_photos_sent_for_retake"]))
    print("decision    n=%d  %-30s wrong_approve %3d  wrong_reject %3d  human %3d  COST %d" % (
        d["n"], "decide()", d["wrong_approvals"], d["wrong_rejections"], d["human_reviews"], d["total_cost"]))
    d_ocr = r.get("document_ocr")
    print("ocr         " + ("%s on %d synthetic cards: CNIC exact %.2f, name %.2f, father %.2f, DOB %.2f, %.0f ms per photo" % (
        d_ocr["engine"], d_ocr["n"], d_ocr["cnic_exact"], d_ocr["name_exact"], d_ocr["father_name_exact"], d_ocr["date_of_birth_exact"],
        d_ocr["median_ms_per_photo"]) if d_ocr else "no OCR engine installed (pip install \"./ai[ocr]\"): the photo gets the quality check only"))
    sc = r["scenarios"]
    print("scenarios   n=%d  accuracy %.3f  wrong_approve %d  wrong_reject %d  human %d  COST %d  spoken claims auto-handled %d/%d  mismatches %s" % (
        sc["n"], sc["accuracy"], sc["wrong_approvals"], sc["wrong_rejections"], sc["human_reviews"], sc["total_cost"],
        sc["spoken_claims_auto_handled"], sc["spoken_claims"], [m["id"] for m in sc["mismatches"]]))
    c = r["classifier"]
    print("named      false_alarm_rate %.3f  genuine_to_unsure %.3f  missed_scam_rate %.3f (as unsure %d, as genuine %d)" % (
        c["false_alarm_rate"], c["genuine_to_unsure_rate"], c["missed_scam_rate"], c["missed_scam_as_unsure"], c["missed_scam_as_genuine"]))
    print("latency ms  " + "  ".join("%s %.3f" % (k, v) for k, v in r["latency_ms"].items()) + "   | llm: %s" % r["llm_cost"]["llm"])
    cv = r.get("classifier_cv")
    if cv:
        print("classifier cv (5-fold)  rules: accuracy %.3f missed %.3f false_alarm %.3f   rules + text model: accuracy %.3f missed %.3f false_alarm %.3f" % (
            cv["rules"]["accuracy"], cv["rules"]["missed_scam_rate"], cv["rules"]["false_alarm_rate"],
            cv["hybrid"]["accuracy"], cv["hybrid"]["missed_scam_rate"], cv["hybrid"]["false_alarm_rate"]))
    cc = r["cost_curve"]
    print("cost curve  cheapest auto_handle_min %.2f (cost %.0f per %d cases); chosen %.2f (cost %.0f); chosen is cheapest: %s" % (
        cc["best_auto_handle_min"], cc["best_cost"], cc["cases"], cc["chosen_auto_handle_min"], cc["chosen_cost"], cc["chosen_is_cheapest"]))
    if "extraction_llm" in r:
        x = r["extraction_llm"]
        for label in ("offline", "llm_assisted"):
            s = {k: ("n/a" if v is None else "%.3f" % v) for k, v in x[label].items() if k != "n"}
            print("natural wording n=%d %-13s understood %s  name %s  refusal %s  INVENTED %s   (llm: %s)" % (
                x["n"], label, s["understood_rate"], s["name_accuracy"], s["refusal_rate"], s["invented_claim_rate"], x["llm_status"]))
    for name, b in d["baselines"].items():
        print("%-20s %-30s wrong_approve %3d  wrong_reject %3d  human %3d  COST %d" % ("", name, b["wrong_approvals"], b["wrong_rejections"], b["human_reviews"], b["total_cost"]))


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the real Bharosa AI functions on synthetic data")
    parser.add_argument("--split", default="all", choices=["train", "val", "test", "all"],
                        help="default all: the sets are tiny, so a 20%% test split alone is not meaningful")
    parser.add_argument("--out", default=str(OUT_PATH))
    parser.add_argument("--no-images", action="store_true", help="skip the (slower) photo blur evaluation")
    parser.add_argument("--chart", default=str(CHART_PATH), help="where to write the cost-per-threshold chart (PNG)")
    parser.add_argument("--no-chart", action="store_true", help="do not draw the chart")
    parser.add_argument("--llm", action="store_true", help="also compare offline vs LLM-assisted extraction (reads ai/.env, calls the LLM)")
    args = parser.parse_args(argv)
    if args.llm:
        _load_dotenv(AI_DIR / ".env")
        if not llm.enabled():
            print("--llm needs a working LLM setup; status: %s" % llm.status())
            return 2
    result = run_eval(args.split, images=not args.no_images, compare_llm=args.llm)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    _print(result)
    print("wrote %s" % args.out)
    if not args.no_chart:
        draw_cost_chart(result["cost_curve"], Path(args.chart))
        print("wrote %s" % args.chart)
    return 0


if __name__ == "__main__":
    sys.exit(main())
