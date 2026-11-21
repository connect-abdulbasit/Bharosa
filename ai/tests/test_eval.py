"""The evaluation script: result shape, cost arithmetic, safety properties and the written file."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

from bharosa_ai import llm
from contracts.schemas import EvalResults

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_eval_under_test", _ROOT / "eval" / "run_eval.py")
run_eval = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_eval)


@pytest.fixture(scope="module")
def result():
    return run_eval.run_eval("all", images=False)


def test_result_validates_against_the_contract(result):
    EvalResults(**result)
    assert result["cost_assumptions"] == {"wrong_approval": 10, "wrong_rejection": 5, "human_review": 1}
    assert result["model_version"] and result["notes"]


def test_total_cost_is_the_weighted_sum(result):
    d = result["decision"]
    assert result["total_cost"] == d["total_cost"] == 10 * d["wrong_approvals"] + 5 * d["wrong_rejections"] + d["human_reviews"]
    for b in d["baselines"].values():
        assert b["total_cost"] == 10 * b["wrong_approvals"] + 5 * b["wrong_rejections"] + b["human_reviews"]


def test_decide_is_safe_and_cheaper_than_every_baseline(result):
    d = result["decision"]
    assert d["wrong_approvals"] <= 0.01 * d["n"]  # noise on the inputs may rarely push a weak case over the line
    assert d["total_cost"] < min(b["total_cost"] for b in d["baselines"].values())
    assert d["baselines"]["claim_confidence_only"]["wrong_approvals"] > 10 * max(d["wrong_approvals"], 1)  # the naive rule really is unsafe


def test_the_classifier_never_swaps_scam_and_genuine(result):
    assert result["classifier"]["dangerous_error_rate"] == 0.0
    assert result["classifier"]["precision_scam"] == 1.0


def test_extraction_never_invents_a_claim_from_bad_speech(result):
    e = result["extraction"]
    assert e["invented_claim_rate"] == 0.0 and e["refusal_rate"] == 1.0


def test_matching_false_matches_stay_rare(result):
    assert result["matching"]["false_match_rate"] <= 0.05 and result["matching"]["top1_accuracy"] >= 0.9


def test_splits_are_stable_disjoint_and_cover_everything():
    keys = ["msg-%d" % i for i in range(200)]
    first = [run_eval.CASES.split_of(k) for k in keys]
    assert first == [run_eval.CASES.split_of(k) for k in keys]
    assert set(first) == {"train", "val", "test"}
    n = len(run_eval.CASES.MESSAGES)
    sizes = [len(run_eval._pick(run_eval.CASES.MESSAGES, "msg", s)) for s in ("train", "val", "test")]
    assert sum(sizes) == n and len(run_eval._pick(run_eval.CASES.MESSAGES, "msg", "all")) == n


def test_the_script_writes_the_file_the_backend_reads(tmp_path):
    out = tmp_path / "eval_results.json"
    assert run_eval.main(["--out", str(out), "--no-images", "--split", "test", "--chart", str(tmp_path / "chart.png")]) == 0
    assert (tmp_path / "chart.png").exists()
    EvalResults(**json.loads(out.read_text(encoding="utf-8")))
    assert run_eval.OUT_PATH == _ROOT / "eval" / "eval_results.json"  # ai/eval/eval_results.json: the path backend config.py reads


def test_the_default_eval_is_offline_even_if_the_llm_is_configured(monkeypatch):
    monkeypatch.setenv("AI_USE_LLM", "1")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setattr(llm, "_post", lambda body: pytest.fail("the default evaluation must never call the LLM"))
    run_eval.run_eval("all", images=False)
    assert os.environ["AI_USE_LLM"] == "1"  # and it puts the environment back


def test_llm_comparison_shows_what_the_llm_adds_without_inventing(monkeypatch):
    monkeypatch.setenv("AI_USE_LLM", "1")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-a-real-secret")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    expected = dict(run_eval.CASES.NATURAL_TRANSCRIPTS)

    def fake_post(body):
        user = body["messages"][1]["content"]
        for text, exp in expected.items():
            if text in user and "error" not in exp:
                return {"choices": [{"message": {"content": json.dumps({"claim_type": exp["type"], "name": exp["name"]})}}],
                        "usage": {"total_tokens": 100}}
        return {"choices": [{"message": {"content": json.dumps({"claim_type": None, "name": None})}}], "usage": {"total_tokens": 100}}

    monkeypatch.setattr(llm, "_post", fake_post)
    monkeypatch.setenv("LLM_PRICE_PER_1M_TOKENS", "2")
    out = run_eval.eval_llm_comparison()
    cost = out["llm_cost"]
    assert cost["calls"] == 5 and cost["tokens"] == 500 and cost["calls_per_case"] == round(5 / 7, 3)  # only the 5 that need help call the LLM
    assert cost["cost_per_case_usd"] == round(500 / 1e6 * 2 / 7, 6) and cost["tokens_per_call"] == 100.0
    assert out["offline"]["understood_rate"] == 0.0          # the offline parser cannot finish any of the natural wordings
    assert out["llm_assisted"]["understood_rate"] == 1.0 and out["llm_assisted"]["name_accuracy"] == 1.0
    assert out["offline"]["invented_claim_rate"] == 0.0 and out["llm_assisted"]["invented_claim_rate"] == 0.0
    assert out["llm_assisted"]["refusal_rate"] == 1.0 and out["llm_status"] == "on"


def test_llm_flag_refuses_to_run_without_a_working_setup(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_eval, "_load_dotenv", lambda path: None)  # never read the developer's real ai/.env in a test
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    out = tmp_path / "x.json"
    assert run_eval.main(["--llm", "--out", str(out)]) == 2
    assert not out.exists() and "needs a working LLM setup" in capsys.readouterr().out


def test_dotenv_loader_sets_missing_variables_only_and_prints_nothing(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text("# comment\nTEST_ENV_A=one\nTEST_ENV_B='two'\nnot a pair\nTEST_ENV_KEEP=file\n", encoding="utf-8")
    os.environ["TEST_ENV_KEEP"] = "process"
    try:
        run_eval._load_dotenv(path)
        assert (os.environ["TEST_ENV_A"], os.environ["TEST_ENV_B"], os.environ["TEST_ENV_KEEP"]) == ("one", "two", "process")
        assert capsys.readouterr().out == ""
    finally:
        for name in ("TEST_ENV_A", "TEST_ENV_B", "TEST_ENV_KEEP"):
            os.environ.pop(name, None)


def test_the_numbers_judges_ask_for_are_saved_under_their_own_names(result):
    c, conf = result["classifier"], result["confusion"]
    genuine, scam = sum(conf["genuine"].values()), sum(conf["scam"].values())
    assert c["false_alarm_rate"] == round(conf["genuine"].get("scam", 0) / genuine, 4) == 0.0
    assert c["genuine_to_unsure_rate"] == round(conf["genuine"].get("unsure", 0) / genuine, 4)
    assert c["missed_scam_rate"] == round((scam - conf["scam"]["scam"]) / scam, 4) and c["missed_scam_rate"] > 0
    assert c["missed_scam_as_unsure"] + c["missed_scam_as_genuine"] == scam - conf["scam"]["scam"]
    assert c["missed_scam_as_genuine"] == 0.0


def test_latency_is_measured_for_every_function(result):
    lat = result["latency_ms"]
    assert {"classify_message", "match_person", "extract_claim", "decide", "explain"} <= set(lat)
    assert all(v > 0 for v in lat.values()) and lat["decide"] < 50 and lat["classify_message"] < 50


def test_llm_cost_is_off_by_default_and_never_holds_a_secret(result):
    cost = result["llm_cost"]
    assert cost["llm"] == "off" and cost["cost_per_case_usd"] is None and cost["calls_per_case"] == 0.0
    assert "key" not in json.dumps(cost).lower()


def test_the_default_classifier_score_is_rules_only_and_the_text_model_is_reported_by_cross_validation(result, monkeypatch):
    cv = result["classifier_cv"]
    if cv is None:  # scikit-learn is a dev-only extra
        pytest.skip("scikit-learn not installed")
    assert cv["rules"]["accuracy"] == result["classifier"]["accuracy"]            # the same rule model, scored the same way
    assert cv["hybrid"]["missed_scam_rate"] <= cv["rules"]["missed_scam_rate"] and cv["hybrid"]["false_alarm_rate"] == 0.0
    monkeypatch.setenv("AI_USE_ML", "1")
    assert run_eval.run_eval("all", images=False)["classifier"]["accuracy"] == result["classifier"]["accuracy"]  # forced off while it runs
    assert os.environ["AI_USE_ML"] == "1"


def test_fifty_labelled_end_to_end_scenarios_run_through_the_real_functions(result):
    sc = result["scenarios"]
    cases = run_eval._load("decision_cases").CASES
    assert sc["n"] == len(cases) == 50 and len({c["id"] for c in cases}) == 50
    assert sc["accuracy"] >= 0.95 and sc["wrong_approvals"] == 0 and sc["wrong_rejections"] == 0
    assert sc["total_cost"] == 10 * sc["wrong_approvals"] + 5 * sc["wrong_rejections"] + sc["human_reviews"]
    assert sc["spoken_claims"] == 40 and sc["spoken_claims_auto_handled"] == 0   # extraction is capped at 0.80: a spoken claim always needs more
    assert {c["expected"] for c in cases} == {"auto_handle", "ask_more", "send_to_human"}


@pytest.mark.parametrize("cid,expected", [("s01", "ask_more"), ("s16", "send_to_human"), ("s22", "send_to_human"), ("s30", "send_to_human"),
                                          ("s34", "send_to_human"), ("s41", "auto_handle"), ("s45", "ask_more"), ("s49", "ask_more")])
def test_individual_scenarios_behave_as_the_policy_says(cid, expected):
    case = next(c for c in run_eval._load("decision_cases").CASES if c["id"] == cid)
    assert run_eval._scenario_action(case) == expected


def test_the_scenario_evaluation_can_fail(monkeypatch):
    cases = run_eval._load("decision_cases").CASES
    wrong = dict(next(c for c in cases if c["id"] == "s41"), expected="send_to_human")  # a deliberately wrong label must show up as a mismatch
    monkeypatch.setattr(run_eval, "_load", lambda name: type("M", (), {"CASES": [wrong]}))
    out = run_eval.eval_scenarios()
    assert out["accuracy"] == 0.0 and out["mismatches"][0]["id"] == "s41" and out["wrong_approvals"] == 1


def test_cost_curve_shows_0_90_is_the_cheapest_auto_approve_threshold(result):
    c = result["cost_curve"]
    assert c["best_auto_handle_min"] == 0.9 and c["chosen_is_cheapest"] and c["chosen_cost"] == c["best_cost"]
    costs = {r["threshold"]: r["total_cost"] for r in c["auto_handle_min"]}
    assert costs[0.9] < costs[0.85] and costs[0.9] < costs[0.95] and costs[0.9] < costs[0.5] and costs[0.9] < costs[1.0]
    assert c["breakeven"] == {"approve_vs_human": 0.9, "reject_vs_human": 0.2}
    assert "calibrated" in c["assumption"]


def test_the_lower_threshold_is_flat_and_marked_unpriced(result):
    rows = result["cost_curve"]["ask_more_min"]
    assert len({r["total_cost"] for r in rows}) == 1 and all(r["priced"] is False for r in rows)
    assert "cannot be proven by cost" in result["cost_curve"]["ask_more_min_note"]


def test_cheapest_action_by_confidence_follows_the_costs(result):
    by = {r["confidence"]: r for r in result["cost_curve"]["expected_cost_by_confidence"]}
    cheapest = lambda r: min(("reject", "human_review", "approve"), key=lambda k: r[k])  # noqa: E731
    assert cheapest(by[0.1]) == "reject" and cheapest(by[0.6]) == "human_review" and cheapest(by[0.95]) == "approve"


def test_the_chart_is_a_real_png(result, tmp_path):
    from PIL import Image

    path = tmp_path / "cost_chart.png"
    run_eval.draw_cost_chart(result["cost_curve"], path)
    img = Image.open(path)
    assert img.format == "PNG" and img.size[0] >= 1200 and img.size[1] >= 1000
    assert len(img.convert("RGB").getcolors(maxcolors=100000)) > 8  # not a blank picture


def test_the_ocr_block_is_none_without_an_engine_and_the_blur_gate_never_runs_ocr(monkeypatch):
    monkeypatch.setenv("AI_USE_OCR", "0")
    assert run_eval.eval_document_ocr() is None
    monkeypatch.setenv("AI_USE_OCR", "1")
    seen = []
    from bharosa_ai import ocr
    monkeypatch.setattr(ocr, "engine_name", lambda: seen.append(os.environ["AI_USE_OCR"]) or None)
    run_eval.eval_documents()
    assert set(seen) <= {"0"} and os.environ["AI_USE_OCR"] == "1"   # the gate is scored with OCR off, and the environment is put back


def test_ocr_accuracy_on_generated_cards_with_the_real_engine(monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.setenv("AI_OCR_ENGINE", "rapidocr")
    out = run_eval.eval_document_ocr(limit=1)
    assert out["engine"] == "rapidocr" and out["n"] == 2
    assert out["cnic_exact"] == out["name_exact"] == out["father_name_exact"] == out["date_of_birth_exact"] == out["format_ok_rate"] == 1.0
    assert 0.80 <= out["average_confidence"] <= 0.85 and out["median_ms_per_photo"] > 0 and "synthetic" in out["note"]


def test_document_gate_on_generated_cards():
    d = run_eval.eval_documents()
    assert d["good_photos_accepted"] >= 0.9 and d["bad_photos_sent_for_retake"] >= 0.9
