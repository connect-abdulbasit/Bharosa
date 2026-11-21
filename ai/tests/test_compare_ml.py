"""eval/compare_ml.py: the cross-validated comparison of the rule model, the text model and the hybrid (skipped without scikit-learn)."""
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")

AI_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("compare_ml_under_test", AI_DIR / "eval" / "compare_ml.py")
compare_ml = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare_ml)


@pytest.fixture(scope="module")
def result():
    return compare_ml.compare(folds=5)


def test_all_three_models_are_scored_on_every_message(result):
    assert result["n"] == 150 and result["rules"]["n"] == result["hybrid"]["n"] == 150.0
    for key in ("rules", "hybrid"):
        m = result[key]
        assert all(0.0 <= m[k] <= 1.0 for k in ("accuracy", "false_alarm_rate", "genuine_to_unsure_rate", "missed_scam_rate", "scam_precision", "ece"))


def test_the_hybrid_only_adds_catches_and_never_adds_false_alarms(result):
    rules, hybrid = result["rules"], result["hybrid"]
    assert hybrid["missed_scam_rate"] <= rules["missed_scam_rate"]            # it can only turn an unsure into a scam
    assert hybrid["false_alarm_rate"] <= rules["false_alarm_rate"] + 1e-9     # genuine messages stay genuine
    assert hybrid["missed_scam_as_genuine"] == rules["missed_scam_as_genuine"]


def test_the_rules_row_is_the_rule_classifier_without_the_text_model(result):
    assert result["rules"]["accuracy"] == pytest.approx(0.9533, abs=0.001) and result["rules"]["false_alarm_rate"] == 0.0


def test_text_model_alone_is_reported_as_scam_versus_rest(result):
    t = result["text_model_alone"]
    assert set(t) == {"scam_recall_at_0.5", "genuine_called_scam_at_0.5", "unsure_called_scam_at_0.5", "ece"}


def test_deterministic_and_the_script_writes_json(result, tmp_path):
    assert compare_ml.compare(folds=5) == result
    out = tmp_path / "ml.json"
    assert compare_ml.main(["--out", str(out)]) == 0 and json.loads(out.read_text(encoding="utf-8"))["n"] == 150
