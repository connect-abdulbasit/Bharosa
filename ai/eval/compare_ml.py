"""Dev-only comparison: the TF-IDF + logistic regression text model (CalibratedClassifierCV) versus the rule classifier, and the hybrid.

Needs scikit-learn (`pip install "./ai[ml]"`); bharosa_ai itself does NOT depend on it. The runtime text model is the exported copy of the
model built here (eval/train_classifier.py), scored in pure Python by bharosa_ai/classify_ml.py. With only 150 synthetic messages a
train/test split would mean little, so the text model is scored by 5-fold stratified cross-validation (every message is predicted by a model
that never saw it); the rule model is not trained, so it is scored directly. The hybrid is what classify.py does: keep the rule label,
except a rule `unsure` from a non-official sender becomes `scam` when the text model gives p_scam >= 0.85.
Writes ai/eval/ml_comparison.json.

Run:  python ai/eval/compare_ml.py [--out PATH] [--folds 5]

HONESTY: author-written synthetic data; the numbers are an upper bound for every model. The model shipped in bharosa_ai is trained on ALL
150 messages, so the shipped hybrid scores near-perfectly on them: only these cross-validated numbers estimate how it does on new messages.
"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
AI_DIR = HERE.parent
for _p in (str(AI_DIR.parent), str(AI_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from bharosa_ai import classify_ml  # noqa: E402
from bharosa_ai.classify import classify_message  # noqa: E402


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metrics(run_eval: Any, gold: List[str], pred: List[str], conf: List[float]) -> Dict[str, float]:
    n = len(gold)
    genuine, scam = gold.count("genuine"), gold.count("scam")
    both = list(zip(gold, pred))
    ece, _ = run_eval._ece([(c, p == g) for g, p, c in zip(gold, pred, conf)])
    r = run_eval._ratio
    return {"n": float(n), "accuracy": r(sum(g == p for g, p in both), n), "false_alarm_rate": r(sum(g == "genuine" and p == "scam" for g, p in both), genuine),
            "genuine_to_unsure_rate": r(sum(g == "genuine" and p == "unsure" for g, p in both), genuine),
            "missed_scam_rate": r(sum(g == "scam" and p != "scam" for g, p in both), scam),
            "missed_scam_as_genuine": float(sum(g == "scam" and p == "genuine" for g, p in both)),
            "scam_precision": r(sum(g == "scam" and p == "scam" for g, p in both), pred.count("scam")), "ece": ece}


def compare(folds: int = 5, seed: int = 2026) -> Dict[str, Any]:
    from sklearn.model_selection import StratifiedKFold

    run_eval = _load(HERE / "run_eval.py", "run_eval_for_ml")
    trainer = _load(HERE / "train_classifier.py", "train_for_ml")
    rows = _load(AI_DIR / "data" / "cases.py", "cases_for_ml").MESSAGES
    docs = [classify_ml.make_doc(t, s) for t, s, *_ in rows]
    gold = [r[2] for r in rows]
    is_scam = [1 if g == "scam" else 0 for g in gold]
    saved = {k: os.environ.get(k) for k in ("AI_USE_LLM", "AI_USE_ML")}
    os.environ["AI_USE_LLM"], os.environ["AI_USE_ML"] = "0", "0"  # the rules are scored WITHOUT the text model; the hybrid is built below from cross-validated scores
    try:
        rules = [classify_message(t, s) for t, s, *_ in rows]
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    p_text = [0.0] * len(rows)
    for train, test in StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(docs, gold):
        vectorizer, classifier = trainer.make_model()
        classifier.fit(vectorizer.fit_transform([docs[i] for i in train]), [is_scam[i] for i in train])
        for i, p in zip(test, classifier.predict_proba(vectorizer.transform([docs[i] for i in test]))[:, 1]):
            p_text[i] = float(p)

    hybrid, hybrid_conf = [], []
    for (text, sender, *_), v, p in zip(rows, rules, p_text):
        if v.label.value == "unsure" and str(sender).strip() != "9090" and p >= classify_ml.UPGRADE_MIN:
            hybrid.append("scam"), hybrid_conf.append(min(max(p, 0.5), 0.95))
        else:
            hybrid.append(v.label.value), hybrid_conf.append(float(v.confidence))
    scam_n = sum(is_scam)
    text_alone = {  # scam-versus-the-rest only: the text model has no "unsure"
        "scam_recall_at_0.5": run_eval._ratio(sum(1 for y, p in zip(is_scam, p_text) if y and p >= 0.5), scam_n),
        "genuine_called_scam_at_0.5": run_eval._ratio(sum(1 for g, p in zip(gold, p_text) if g == "genuine" and p >= 0.5), gold.count("genuine")),
        "unsure_called_scam_at_0.5": run_eval._ratio(sum(1 for g, p in zip(gold, p_text) if g == "unsure" and p >= 0.5), gold.count("unsure")),
        "ece": run_eval._ece([(max(p, 1 - p), (p >= 0.5) == bool(y)) for y, p in zip(is_scam, p_text)])[0]}
    return {"n": len(rows), "folds": folds, "upgrade_min": classify_ml.UPGRADE_MIN,
            "rules": _metrics(run_eval, gold, [v.label.value for v in rules], [float(v.confidence) for v in rules]),
            "text_model_alone": text_alone,
            "hybrid": _metrics(run_eval, gold, hybrid, hybrid_conf),
            "note": "synthetic, author-written messages; the text model is cross-validated; an upper bound. The model shipped in bharosa_ai is "
                    "trained on all messages, so only these numbers estimate performance on new messages."}


def _print(r: Dict[str, Any]) -> None:
    print("%d messages, %d-fold cross-validation (synthetic data: upper bound)" % (r["n"], r["folds"]))
    print("%-22s %9s %11s %14s %10s %10s %6s" % ("model", "accuracy", "false_alarm", "genuine>unsure", "missed", "precision", "ece"))
    for key, label in (("rules", "rules only"), ("hybrid", "rules + text model")):
        m = r[key]
        print("%-22s %9.3f %11.3f %14.3f %10.3f %10.3f %6.3f" % (label, m["accuracy"], m["false_alarm_rate"], m["genuine_to_unsure_rate"],
                                                                m["missed_scam_rate"], m["scam_precision"], m["ece"]))
    t = r["text_model_alone"]
    print("text model alone (scam vs rest, p>=0.5): recall %.3f, genuine called scam %.3f, unsure called scam %.3f, ece %.3f" % (
        t["scam_recall_at_0.5"], t["genuine_called_scam_at_0.5"], t["unsure_called_scam_at_0.5"], t["ece"]))


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare the TF-IDF + logistic regression text model with the rule classifier (dev only)")
    parser.add_argument("--out", default=str(HERE / "ml_comparison.json"))
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        result = compare(args.folds)
    except ImportError:
        print('scikit-learn is not installed: pip install "./ai[ml]"')
        return 2
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    _print(result)
    print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
