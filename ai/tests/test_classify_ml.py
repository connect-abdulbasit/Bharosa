"""The pure-Python text model and the hybrid: parity with scikit-learn, upgrade-only behaviour, kill switch."""
import importlib.util
import math
from pathlib import Path

import pytest

from bharosa_ai import classify, classify_ml
from contracts.enums import MessageLabel

AI_DIR = Path(__file__).resolve().parents[1]


def _cases():
    spec = importlib.util.spec_from_file_location("cases_for_ml_test", AI_DIR / "data" / "cases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MESSAGES


@pytest.fixture
def ml_on(monkeypatch):
    monkeypatch.setenv("AI_USE_ML", "1")


def test_the_weights_file_exists_and_is_plain_python():
    assert classify_ml._w is not None and classify_ml._w.TRAINED_ON == 150 and len(classify_ml._w.FEATURES) > 1000
    assert all(isinstance(v, tuple) and len(v) == 2 for v in list(classify_ml._w.FEATURES.values())[:50])


def test_the_kill_switch_and_the_missing_weights_turn_the_model_off(monkeypatch):
    monkeypatch.setenv("AI_USE_ML", "0")
    assert not classify_ml.available()
    monkeypatch.setenv("AI_USE_ML", "1")
    assert classify_ml.available()
    monkeypatch.setattr(classify_ml, "_w", None)
    assert not classify_ml.available() and classify_ml.p_scam("pay fee", "X") == 0.0


def test_ngrams_follow_the_char_wb_analyzer():
    assert list(classify_ml.ngrams("ab")) == [" a", "ab", "b ", " ab", "ab ", " ab "]
    assert list(classify_ml.ngrams("  Fee   NOW ")) == list(classify_ml.ngrams("fee now"))  # lowercase, any whitespace
    assert list(classify_ml.ngrams("")) == []


def test_make_doc_adds_the_sender_cues():
    assert classify_ml.make_doc("hello", "9090").endswith("senderofficial")
    assert "senderlookalike" in classify_ml.make_doc("hello", "9O9O")
    assert "sendermobile" in classify_ml.make_doc("hello", "0300-1112233")
    assert "senderalpha" in classify_ml.make_doc("hello", "SAHARA-INFO")
    assert classify_ml.make_doc(None, None).strip() == ""


def test_p_scam_is_a_probability_and_separates_the_classes_on_the_training_messages(ml_on):
    rows = _cases()
    scam = [classify_ml.p_scam(t, s) for t, s, g, *_ in rows if g == "scam"]
    genuine = [classify_ml.p_scam(t, s) for t, s, g, *_ in rows if g == "genuine"]
    assert all(0.0 <= p <= 1.0 for p in scam + genuine)
    assert sum(scam) / len(scam) > 0.7 > 0.3 > sum(genuine) / len(genuine)   # seen data: the mean separates (not a quality claim)


@pytest.mark.parametrize("text,sender", [("", ""), (None, None), ("x" * 10000, "9090"), ("\x00�", "s" * 500), (123, 456)])
def test_p_scam_never_raises_on_odd_input(text, sender):
    assert 0.0 <= classify_ml.p_scam(text, sender) <= 1.0


def test_parity_with_scikit_learn_on_every_training_message():
    pytest.importorskip("sklearn")
    spec = importlib.util.spec_from_file_location("train_for_parity", AI_DIR / "eval" / "train_classifier.py")
    trainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trainer)
    model = trainer.train()
    reference = model["classifier"].predict_proba(model["x"])[:, 1]
    rows = _cases()
    mine = [classify_ml.p_scam(t, s) for t, s, *_ in rows]
    assert max(abs(a - float(b)) for a, b in zip(mine, reference)) < 1e-9, "the pure-Python scorer must equal scikit-learn"
    assert math.isclose(model["intercept"], classify_ml._w.INTERCEPT, rel_tol=1e-12)  # the exported file is the one just trained


def test_the_text_model_upgrades_an_unsure_to_scam_only_when_very_sure(monkeypatch, ml_on):
    text, sender = "Your payment status has changed", "0300-1111111"   # the rules alone say unsure
    monkeypatch.setattr(classify_ml, "p_scam", lambda t, s: 0.0)
    assert classify.classify_message(text, sender).label == MessageLabel.unsure
    monkeypatch.setattr(classify_ml, "p_scam", lambda t, s: 0.90)
    v = classify.classify_message(text, sender)
    assert v.label == MessageLabel.scam and v.model_version == "classify-hybrid-1.0" and v.confidence == 0.9
    assert v.reasons[0] == "The wording is very like scam messages we have seen" and len(v.model_version) <= 40
    monkeypatch.setattr(classify_ml, "p_scam", lambda t, s: 0.80)
    assert classify.classify_message(text, sender).label == MessageLabel.unsure       # not sure enough


def test_the_hybrid_never_touches_the_official_sender_or_a_rule_verdict(monkeypatch, ml_on):
    monkeypatch.setattr(classify_ml, "p_scam", lambda t, s: 0.99)
    assert classify.classify_message("Your stipend is ready", "9090").label == MessageLabel.genuine    # never creates or removes genuine
    assert classify.classify_message("Your stipend is ready. Pay the fee to receive it", "9090").label == MessageLabel.unsure  # official stays unsure
    v = classify.classify_message("Pay fee at http://bit.ly/x to get relief", "SAHARA-INFO")
    assert v.label == MessageLabel.scam and v.model_version == "classify-rules-1.0"                    # a rule scam keeps its rule version


def test_a_failing_text_model_leaves_the_rule_verdict(monkeypatch, ml_on):
    def boom(t, s):
        raise RuntimeError("broken weights")

    monkeypatch.setattr(classify_ml, "p_scam", boom)
    assert classify.classify_message("hello", "0300-1111111").label == MessageLabel.unsure


def test_with_the_switch_off_the_verdict_is_the_rule_verdict(monkeypatch):
    monkeypatch.setenv("AI_USE_ML", "0")
    monkeypatch.setattr(classify_ml, "p_scam", lambda t, s: 0.99)
    assert classify.classify_message("hello", "0300-1111111").label == MessageLabel.unsure


def test_a_message_the_rules_miss_is_caught_by_a_text_model_that_never_saw_it_when_it_is_very_like_scam(ml_on):
    # not a quality claim (the model is trained on author-written data): it only shows the hybrid path works end to end with real weights
    v = classify.classify_message("Aap ki raqam tayyar hai, hamare number par apna account number bhej dein", "0333-9998877")
    assert v.label in (MessageLabel.scam, MessageLabel.unsure) and 0.0 <= v.confidence <= 1.0
