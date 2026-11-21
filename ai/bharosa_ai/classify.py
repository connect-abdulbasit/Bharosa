"""classify_message: scam / genuine / unsure for an SMS, from the text and the sender. Local, offline, never raises.

A transparent cue-weight model: every cue found adds log-odds toward "scam", official-sender evidence subtracts, and a
sigmoid turns the total into p_scam. Cues are written for English, Roman Urdu and Urdu script.
Safety rules, so the classifier never over-claims:
- `genuine` needs the exact official code 9090 AND no scam cue at all; any other sender can be at most `unsure`
  (the backend checks the full official sender list and may downgrade or upgrade further);
- a sender that looks like 9090 (9O9O, 9o9o) is a strong scam signal;
- warnings such as "never share your PIN" are not scam cues (negation is respected for private-information cues);
- when the evidence is thin or mixed the answer is `unsure`, with a confidence between 0.4 and 0.6;
- HYBRID: a pure-Python text model (classify_ml.py, TF-IDF + logistic regression + calibration, weights exported from scikit-learn) may
  upgrade an `unsure` to `scam` when it is at least 0.85 sure and the sender is not the official code. It never creates a `genuine`,
  never touches a rule `scam`/`genuine`, and AI_USE_ML=0 turns it off. Such results carry model_version "classify-hybrid-1.0".
ponytail: regex cue lists cannot see through deliberate obfuscation (f.e.e, spaced letters). Upgrade path: more cues or a
learned model, evaluated with eval/run_eval.py.
"""
import math
import re
import unicodedata
from typing import List, Tuple

from bharosa_ai import classify_ml
from contracts.ai_interface import MessageVerdict
from contracts.enums import MessageLabel

MODEL_VERSION = "classify-rules-1.0"
OFFICIAL_CODE = "9090"
MAX_TEXT = 3000
BIAS = -1.0           # prior log-odds of scam with no evidence at all
OFFICIAL_WEIGHT = -2.0
SCAM_MIN = 0.75       # p_scam at or above this -> scam
GENUINE_MAX = 0.20    # p_scam at or below this (official sender, no cue) -> genuine
_PLATT = (1.0, 0.0)   # confidence calibration (slope, intercept on the logit): the identity, not fitted; eval/run_eval.py reports the calibration error

_NEGATORS = re.compile(r"\b(?:do not|don't|dont|never|no|not|without|nahi|nahin|na|mat|kabhi|beware|fake|fraud|fraudulent|scams?|jaali|hoshiyar|careful)\b|"
                       r"نہ|نہیں|مت|کبھی|جعلی|ہوشیار|احتیاط")
# warning context only (no plain "no"/"not"): a message that warns about scams mentions fees and OTPs without asking for them
_WARNING = re.compile(r"\b(?:beware|fake|fraud|fraudulent|scams?|jaali|hoshiyar|never ask|will never|kabhi nahi)\b|جعلی|ہوشیار|احتیاط|کبھی\s*نہیں")
_SENTENCE_END = ".!?۔\n"
_SAFE_NO_FEE = re.compile(r"\b(?:no|zero|without)\s+(?:processing\s+)?(?:fee|fees|charges?)\b|\bfree of (?:cost|charge)\b|"
                          r"\b(?:never|do not|don't|dont)\s+(?:pay|send|give)\s+(?:any\s+)?(?:fee|fees|charges?|money)\b|"
                          r"\bkoi\s+(?:fees?|charges?)\s+nahi\b|کوئی\s*فیس\s*نہیں")

# (reason, weight, pattern, check): check is False (always counts), True (not when negated or warned about) or "warn" (not when warned about)
_CUES: List[Tuple[str, float, "re.Pattern[str]", object]] = [(r, w, re.compile(p), n) for r, w, p, n in [
    ("Contains a shortened link", 2.5, r"\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|cutt\.ly|rb\.gy|shorturl\.at)", False),
    ("Contains a link", 1.5, r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|info|xyz|top|club|online|site|link|app)\b|لنک", False),
    ("Asks you to pay a fee or send money", 2.5,
     r"\b(?:fee|fees|charges|advance)\b|\b(?:send|deposit|transfer|submit)\s+(?:rs\.?|pkr|rupees|money)|"
     r"\b(?:paisay|paise|pese|rupay|raqam)\s+(?:bhej(?:\s+(?:den|dein|do|dijiye|dena)|ain|en|iye|o)\b|jama\s+(?:karwa|karain|karen|karao|kara))|"
     r"\bjama\s+(?:karwa|karain|karen|karao|kara)\w*|"
     r"فیس|جمع\s*(?:کروا|کرا|کریں|کرو)\w*|رقم\s*بھیج\w*|پیسے\s*بھیج\w*|ایڈوانس|چارجز", "warn"),  # imperative "deposit!", not "has been deposited"
    ("Mentions a mobile-money app", 1.5, r"\b(?:jazz\s?cash|easy\s?paisa|sadapay|nayapay)\b|جاز\s*کیش|ایزی\s*پیسہ", False),
    ("Asks for your OTP, PIN, password or ID number", 3.0,
     r"\b(?:otp|pin|password|passcode|verification code|cvv)\b|\b(?:cnic|id card)\s*(?:number|no\.?)\b|"
     r"\b(?:otp|pin|code|cnic)\s+(?:batain|bataiye|bhejain|share|dein|den)\w*|او\s?ٹی\s?پی|پاس\s*ورڈ|شناختی\s*کارڈ\s*نمبر", True),
    ("Uses urgency", 1.2,
     r"\b(?:urgent|urgently|immediately|asap|last chance|final (?:notice|warning)|expires?|within \d+ (?:hours?|hrs?|days?)|"
     r"today only|act now|right now|fori|foran|jaldi)\w*|فوری|فوراً|جلدی", False),
    ("Threatens to block or cancel your payment", 1.2,
     r"\b(?:blocked|suspended|cancell?ed|deactivated|will be closed|legal action|warna|block ho)\b|بلاک|ورنہ|معطل", False),
    ("Promises a prize or bonus", 1.5,
     r"\b(?:congratulations|congrats|you(?:'ve| have)? won|winner|lucky|prize|lottery|jackpot|bonus|free gift|claim your|"
     r"mubarak|inam|inaam|lucky draw)\w*|مبارک|انعام|لاٹری", False),
    ("Tells you to click a link or verify your account", 1.5,
     r"\b(?:click|tap|open)\s+(?:here|the link|this link|below)\b|\bverify your\b|\bre-?verify\b|"
     r"\bverification\s+(?:failed|required|needed|pending)\b|\bupdate your (?:details|account|info|cnic)\b|"
     r"\blink\s+par\s+click\b|لنک\s*پر\s*کلک|تصدیق\s*کر", False),
    ("Tells you to call or reply to claim something", 1.5,
     r"\b(?:call|reply|contact|message)\b[^.!?]{0,40}\bto (?:claim|receive|get|join|release)\b", False),
]]
_PROGRAMME_NAME = re.compile(r"sahara|relief|gov")
_MOBILE = re.compile(r"^\+?[\d\s-]{10,}$")
_MIXED_GLYPHS = re.compile(r"(?<![a-z])l(?=[A-Z])|(?<=[a-z])I(?=[a-z])|(?<=[A-Za-z])[01](?=[A-Za-z])|(?<=\d)[Oo](?=\d)")
_FOLD = str.maketrans({"o": "0", "l": "1", "i": "1", "|": "1", "s": "5", "b": "8"})


def _clean(text: str) -> str:
    s = unicodedata.normalize("NFKC", str(text or ""))[:MAX_TEXT]
    s = "".join(str(unicodedata.decimal(ch)) if unicodedata.category(ch) == "Nd" else ch
                for ch in s if unicodedata.category(ch) not in ("Cf", "Cc") or ch in "\n\t")
    s = s.replace("ي", "ی").replace("ك", "ک")  # Arabic yeh / kaf -> the Urdu letters the cues use
    s = re.sub(r"(.)\1{2,}", r"\1\1", s.casefold())  # "feeees" -> "fees"
    return re.sub(r"\s+", " ", s).strip()


def _before(text: str, start: int) -> str:
    """The text before a cue within its own sentence (at most 80 characters), so "never ask you for money, a PIN or an OTP" covers the OTP."""
    cut = max(text.rfind(c, 0, start) for c in _SENTENCE_END)
    return text[max(cut + 1, start - 80):start]


def _discounted(text: str, start: int, end: int, check: object) -> bool:
    """True when the cue is only mentioned, not asked for: negated ("never share your PIN") or warned about ("beware of fake messages
    asking for fees"). check "warn" looks only for warnings, True also for plain negation (and after the cue: "pin na batain")."""
    warned = bool(_WARNING.search(_before(text, start)))  # a warning word anywhere earlier in the sentence
    if check == "warn":
        return warned
    return warned or bool(_NEGATORS.search(text[max(0, start - 25):start]) or _NEGATORS.search(text[end:end + 25]))  # plain "not/never": close by only


def _calibrate(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return 1 / (1 + math.exp(-(_PLATT[0] * math.log(p / (1 - p)) + _PLATT[1])))


def classify_message(text: str, sender: str) -> MessageVerdict:
    try:
        return _classify(text, sender)
    except Exception:  # the scam check has no try/except above it: never turn odd input into a 500
        return MessageVerdict(label=MessageLabel.unsure, confidence=0.4, model_version=MODEL_VERSION,
                              reasons=["We could not read this message properly, so we are not sure about it."])


def _classify(text: str, sender: str) -> MessageVerdict:
    body = _clean(text)
    raw_sender = str(sender or "").strip()[:80]
    folded_sender = re.sub(r"[^a-z0-9]", "", raw_sender.casefold().translate(_FOLD))
    official = raw_sender == OFFICIAL_CODE
    hits: List[Tuple[float, str]] = []  # (weight, reason)

    scan = _SAFE_NO_FEE.sub(" ", body)  # "no fee needed" must not count as a fee request
    for reason, weight, pattern, check in _CUES:
        for m in pattern.finditer(scan):
            if check and _discounted(scan, m.start(), m.end(), check):
                continue
            hits.append((weight, reason))
            break
    if _SAFE_NO_FEE.search(body):
        hits.append((-1.5, "States that no fee is needed"))

    if not official and raw_sender and folded_sender == OFFICIAL_CODE:
        hits.append((4.0, "Sender '%s' looks like the official code %s but is not it" % (raw_sender, OFFICIAL_CODE)))
    elif not official and _MIXED_GLYPHS.search(raw_sender):
        hits.append((1.5, "The sender name mixes look-alike characters"))
    if not official and _MOBILE.match(raw_sender):
        hits.append((1.0, "Sent from an ordinary mobile number, not an official short code"))
    if not official and _PROGRAMME_NAME.search(raw_sender.casefold()):
        hits.append((0.5, "The sender name imitates the programme"))

    positive = [h for h in hits if h[0] > 0]
    z = BIAS + sum(w for w, _ in hits) + (OFFICIAL_WEIGHT if official else 0.0)
    p_scam = 1 / (1 + math.exp(-z))
    reasons = [r for _, r in sorted(positive, key=lambda h: -h[0])] + [r for w, r in hits if w < 0]

    if p_scam >= SCAM_MIN:
        return MessageVerdict(label=MessageLabel.scam, confidence=round(min(max(_calibrate(p_scam), 0.5), 0.99), 2),
                              reasons=reasons, model_version=MODEL_VERSION)
    if official and not positive and p_scam <= GENUINE_MAX:
        return MessageVerdict(label=MessageLabel.genuine, confidence=round(min(_calibrate(1 - p_scam), 0.95), 2), model_version=MODEL_VERSION,
                              reasons=["Sent from the official code %s" % OFFICIAL_CODE, "No fee, link or request for private information"] + reasons)
    if official:
        reasons.append("It comes from the official code but contains warning signs")
    elif not positive:
        reasons.append("We could not confirm the sender from the message alone")
    reasons = reasons or ["Not enough evidence either way"]
    if not official:  # the text model may only turn an `unsure` into a `scam`, and never for the official code
        try:
            p_text = classify_ml.p_scam(text, sender) if classify_ml.available() else 0.0
        except Exception:
            p_text = 0.0
        if p_text >= classify_ml.UPGRADE_MIN:
            return MessageVerdict(label=MessageLabel.scam, confidence=round(min(max(p_text, 0.5), 0.95), 2), model_version=classify_ml.MODEL_VERSION,
                                  reasons=["The wording is very like scam messages we have seen"] + reasons)
    return MessageVerdict(label=MessageLabel.unsure, confidence=round(0.6 - 0.2 * abs(2 * p_scam - 1), 2), reasons=reasons,
                          model_version=MODEL_VERSION)
