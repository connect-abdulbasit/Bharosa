"""Pure-Python text model for scam messages: character 2-4-gram TF-IDF + logistic regression + sigmoid calibration.

TRAINED OFFLINE with scikit-learn (TfidfVectorizer + LogisticRegression wrapped in CalibratedClassifierCV) by eval/train_classifier.py,
which exports the weights to bharosa_ai/classify_ml_weights.py as plain Python constants. At runtime there is NO scikit-learn and no
data file: this module re-implements sklearn's `char_wb` analyzer and TF-IDF scoring (parity is tested against sklearn).

It answers one question, p_scam(text, sender) in 0..1, and is only used by classify.py to upgrade a rule verdict of `unsure` to `scam`
(never the other way, never for the official sender). AI_USE_ML=0 switches it off.
Trained on the 150 author-written synthetic messages: it has seen them, so score it by the cross-validation in eval/compare_ml.py.
"""
import math
import os
import re
from collections import Counter
from typing import Iterator

try:
    from bharosa_ai import classify_ml_weights as _w
except ImportError:  # the weights file is generated; without it the hybrid is simply off
    _w = None

MODEL_VERSION = "classify-hybrid-1.0"
UPGRADE_MIN = 0.85  # the text model must be at least this sure before it may turn an `unsure` into a `scam`


def available() -> bool:
    return _w is not None and os.environ.get("AI_USE_ML", "1").strip() != "0"


def make_doc(text: str, sender: str) -> str:
    """The message plus sender tokens, so the text model sees the sender cues the rules use. Shared with the training script."""
    s = str(sender or "").strip()
    tokens = []
    if s == "9090":
        tokens.append("senderofficial")
    elif re.sub(r"[^a-z0-9]", "", s.casefold().translate(str.maketrans("olisb", "01158"))) == "9090":
        tokens.append("senderlookalike")
    if re.match(r"^\+?[\d\s-]{10,}$", s):
        tokens.append("sendermobile")
    if s and not re.search(r"\d", s):
        tokens.append("senderalpha")
    return "%s %s" % (str(text or "")[:3000], " ".join(tokens))


def ngrams(doc: str, lo: int = 2, hi: int = 4) -> Iterator[str]:
    """scikit-learn's `char_wb` analyzer: lowercase, split on whitespace, pad each word with a space, take lo..hi-grams inside the word."""
    for word in doc.lower().split():
        w = " " + word + " "
        for n in range(lo, hi + 1):
            offset = 0
            yield w[offset:offset + n]
            while offset + n < len(w):
                offset += 1
                yield w[offset:offset + n]
            if offset == 0:  # a word shorter than n counts once
                break


def p_scam(text: str, sender: str) -> float:
    """Calibrated probability that the message is a scam. Returns 0.0 when the model is not available."""
    if _w is None:
        return 0.0
    counts = Counter(g for g in ngrams(make_doc(text, sender)) if g in _w.FEATURES)
    weighted = {g: (1.0 + math.log(c)) * _w.FEATURES[g][0] for g, c in counts.items()}  # sublinear tf x idf
    norm = math.sqrt(sum(v * v for v in weighted.values())) or 1.0
    z = sum(v / norm * _w.FEATURES[g][1] for g, v in weighted.items()) + _w.INTERCEPT
    return 1.0 / (1.0 + math.exp(max(min(_w.CAL_A * z + _w.CAL_B, 60.0), -60.0)))
