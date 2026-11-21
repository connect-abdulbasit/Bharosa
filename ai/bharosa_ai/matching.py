"""match_person: fuzzy name / CNIC matching for messy data. Pure, offline, deterministic.

Handles transliteration spellings (Muhammad / Mohammad / Mohammed), swapped word order, initials, honorifics, relation
suffixes ("s/o ...") and Urdu script. Names are compared token by token on a phonetic skeleton (vowels dropped, common
digraphs folded). Safety rules, so the AI never silently guesses:
- a token that only matches by spelling (not exactly) caps the confidence below the auto-handle line;
- two candidates that match equally well are ambiguous: no match is returned;
- a CNIC that matches but with a clearly different name, or a CNIC found on nobody, is NOT a match.
`confidence` means: how sure are we that the claimed name and the returned person are the same person.
"""
import datetime
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, NamedTuple, Optional, Tuple

from contracts.ai_interface import MatchResult
from contracts.schemas import PersonRecord

MODEL_VERSION = "match-rules-1.0"
MATCH_MIN = 0.75        # name score needed to call two names the same person (a wrong match costs more than a missed one)
AMBIGUOUS_GAP = 0.05    # two candidates this close (both above MATCH_MIN) cannot be told apart
VARIANT_CAP = 0.88      # spelling-only match: below the 0.90 auto-handle line, so more proof is asked
INITIAL_CAP = 0.75      # an initial ("M. Aslam") only half-identifies a word
MAX_TOKENS, MAX_TOKEN_LEN, MAX_NAME_LEN = 8, 30, 200

_TITLES = {"mr", "mrs", "ms", "miss", "bibi", "begum", "khatoon", "khatun", "sahiba", "sahib", "haji", "hajji", "mohtarma",
           "muhtarma", "بیبی", "بگم", "خاتون"}
_MUHAMMAD = {"muhammad", "mohammad", "mohammed", "muhammed", "mohamad", "muhamad", "mohamed", "muhamed", "mohd", "muhd", "md",
             "محمد"}
_RELATION = re.compile(r"\b(?:s/o|d/o|w/o|wd/o|son of|daughter of|wife of)\b.*$")
_FOLD = {"ي": "ی", "ى": "ی", "ك": "ک", "ۃ": "ہ", "ە": "ہ", "ـ": ""}
_UR = {"ا": "a", "آ": "a", "أ": "a", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t", "ث": "s",
       "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ڈ": "d", "ذ": "z", "ر": "r",
       "ڑ": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t",
       "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g", "ل": "l",
       "م": "m", "ن": "n", "ں": "n", "ھ": "h", "ء": "", "ئ": "i", "ؤ": "u"}
_CAL = [(0.0, 0.0), (0.5, 0.1), (0.7, 0.5), (0.8, 0.65), (0.9, 0.82), (0.95, 0.9), (0.98, 0.95), (1.0, 0.97)]


class Tok(NamedTuple):
    norm: str   # the word as written, case-folded (Muhammad family folded to one form)
    lat: str    # Latin approximation (Urdu script transliterated)
    skel: str   # phonetic skeleton


def _latin(tok: str) -> str:
    out = []
    for i, ch in enumerate(tok):
        if ch == "و":  # waw: consonant at the start, vowel inside
            out.append("w" if i == 0 else "u")
        elif ch in "یے":  # yeh: consonant at the start, vowel inside
            out.append("y" if i == 0 else "i")
        elif ch == "ہ":  # heh: a vowel at the end of a word (Fatima), a consonant inside
            out.append("a" if i == len(tok) - 1 and len(tok) > 1 else "h")
        else:
            out.append(_UR.get(ch, ch))
    return "".join(out)


def _skeleton(lat: str) -> str:
    s = lat
    for a, b in (("ph", "f"), ("gh", "g"), ("kh", "k"), ("sh", "s"), ("ch", "c"), ("zh", "z"), ("th", "t")):
        s = s.replace(a, b)
    s = s.replace("w", "v").replace("q", "k")
    out: List[str] = []
    for i, ch in enumerate(s):
        if ch in "aeiou" or (ch == "y" and i > 0):
            ch = "a" if i == 0 else ""
        if ch and (not out or out[-1] != ch):
            out.append(ch)
    return "".join(out)


def _tokens(name: Optional[str]) -> List[Tok]:
    s = unicodedata.normalize("NFKD", (name or "")[:MAX_NAME_LEN]).casefold()
    s = "".join(_FOLD.get(ch, ch) for ch in s if unicodedata.category(ch) not in ("Mn", "Cf"))
    s = re.sub(r"[^\w\s/]|_|\d", " ", _RELATION.sub(" ", s)).replace("/", " ")
    words = [w[:MAX_TOKEN_LEN] for w in s.split()][:MAX_TOKENS]
    strong = [w for w in words if w not in _TITLES] or words  # titles carry no identity; keep them only if nothing else is left
    toks = []
    for w in strong:
        w = "muhammad" if w in _MUHAMMAD else w
        lat = _latin(w)
        toks.append(Tok(w, lat, _skeleton(lat)))
    return toks


def _sim(a: Tok, b: Tok) -> Tuple[float, bool, bool]:
    """(similarity, spelling-only match, initial match) for two words."""
    if a.norm == b.norm:
        return 1.0, False, False
    if len(a.lat) == 1 or len(b.lat) == 1:
        return (0.6, False, True) if a.lat[:1] == b.lat[:1] else (0.0, False, False)
    if a.skel == b.skel and len(a.skel) >= 2:
        return 0.92, True, False
    raw = SequenceMatcher(None, a.lat, b.lat).ratio()
    if raw >= 0.85:  # one wrong letter: a typo in a long word, but a different name in a short one (Salma / Salman, Asim / Asif)
        return (raw if min(len(a.lat), len(b.lat)) >= 7 else 0.55), False, False
    return raw ** 3, False, False  # a different word scores low


def _align(q: List[Tok], c: List[Tok]) -> Tuple[float, bool, bool]:
    """Order-insensitive, length-weighted word alignment. Words left over on either side count against the score."""
    pairs = []
    for i, a in enumerate(q):
        for j, b in enumerate(c):
            s, variant, initial = _sim(a, b)
            if s >= 0.5:
                pairs.append((s, i, j, variant, initial))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    used_q, used_c = set(), set()
    num = den = 0.0
    variant_only = initial_used = False
    for s, i, j, variant, initial in pairs:
        if i in used_q or j in used_c:
            continue
        used_q.add(i)
        used_c.add(j)
        w = 2.0 if initial else float(max(len(q[i].norm), len(c[j].norm)))
        num, den = num + s * w, den + w
        variant_only, initial_used = variant_only or variant, initial_used or initial
    den += sum(len(t.norm) for k, t in enumerate(q) if k not in used_q) + sum(len(t.norm) for k, t in enumerate(c) if k not in used_c)
    return (num / den if den else 0.0), variant_only, initial_used


def _calibrate(score: float) -> float:
    """Name score -> P(same person). Piecewise linear over the hand-set table _CAL (not fitted; eval/run_eval.py reports the calibration error)."""
    for (x0, y0), (x1, y1) in zip(_CAL, _CAL[1:]):
        if score <= x1:
            return y0 + (y1 - y0) * (score - x0) / (x1 - x0)
    return _CAL[-1][1]


def _digits(cnic: Optional[str]) -> str:
    return re.sub(r"\D", "", cnic or "")


def _best_name(q: List[Tok], person: PersonRecord) -> Tuple[float, bool, bool, str]:
    best = (-1.0, False, False, person.full_name)
    for text in [person.full_name] + list(person.aliases):
        c = _tokens(text)
        if not c:
            continue
        s, variant, initial = _align(q, c)
        if s > best[0]:
            best = (s, variant, initial, text)
    return (max(best[0], 0.0),) + best[1:]


def _dob(value: Optional[str]) -> Optional[str]:
    """A date of birth as YYYY-MM-DD from dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy or yyyy-mm-dd; None when missing or not a real date."""
    m = re.match(r"^\s*(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})\s*$", value or "")
    if not m:
        return None
    a, b, c = m.groups()
    year, month, day = (a, b, c) if len(a) == 4 else (c, b, a)
    try:
        return datetime.date(int(year), int(month), int(day)).isoformat() if len(year) == 4 else None
    except ValueError:
        return None


def _extras(person: PersonRecord, father_name: Optional[str], date_of_birth: Optional[str]) -> Tuple[int, int]:
    """(corroborations, mismatches) from the father's name and the date of birth, counted only when BOTH sides have the value."""
    corroborated = mismatched = 0
    if father_name and person.father_name:
        fq, fc = _tokens(father_name), _tokens(person.father_name)
        if fq and fc:
            f = _align(fq, fc)[0]
            corroborated += f >= 0.85
            mismatched += f < 0.5
    d1, d2 = _dob(date_of_birth), _dob(person.date_of_birth)
    if d1 and d2:
        corroborated += d1 == d2
        mismatched += d1 != d2
    return int(corroborated), int(mismatched)


def match_person(name: str, cnic: Optional[str], candidates: List[PersonRecord], father_name: Optional[str] = None,
                 date_of_birth: Optional[str] = None) -> MatchResult:
    """The optional father_name and date_of_birth (additive: callers that pass only the first three arguments get the same result
    as before) corroborate or contradict a name match. A mismatch caps the confidence at 0.5 (a person looks); corroboration raises
    the spelling-only cap (0.88 to 0.93 with one, 0.95 with both) and can tell two equally good candidates apart."""
    q = _tokens(name)
    if not q:
        return MatchResult(match_id=None, score=0.0, variants=[], confidence=0.0, model_version=MODEL_VERSION)
    scored = sorted(((*_best_name(q, c), c) for c in candidates), key=lambda r: (-r[0], r[4].cnic))
    extra = {r[4].cnic: _extras(r[4], father_name, date_of_birth) for r in scored}
    rank = lambda r: r[0] + 0.06 * (extra[r[4].cnic][0] - extra[r[4].cnic][1])  # noqa: E731  (equals the name score without extras)
    scored.sort(key=lambda r: (-rank(r), r[4].cnic))
    shown = " ".join(t.norm for t in q).title()
    variants = list(dict.fromkeys(v for v in ((name or "").strip()[:60], shown) if v))

    def result(match: Optional[PersonRecord], score: float, conf: float, text: Optional[str] = None) -> MatchResult:
        seen = list(dict.fromkeys(variants + ([text] if text else [])))
        return MatchResult(match_id=match.cnic if match else None, score=round(min(max(score, 0.0), 1.0), 4),
                           variants=seen, confidence=round(min(max(conf, 0.0), 1.0), 4), model_version=MODEL_VERSION)

    best = scored[0] if scored else None
    want = _digits(cnic)
    if cnic and len(want) == 13:  # a CNIC identifies a record, so the name must agree with that record
        hit = next((r for r in scored if _digits(r[4].cnic) == want), None)
        if hit is None:
            return result(None, best[0] if best else 0.0, 0.3)  # nobody has this CNIC: not a match
        score, _, _, text, person = hit
        if extra[person.cnic][1]:  # the card's CNIC is right but the father's name or the date of birth contradicts the record
            return result(None, score, 0.35, text)
        if score >= 0.85:
            return result(person, max(score, 0.9), 0.98, text)
        if score >= MATCH_MIN:
            return result(person, score, 0.9 * _calibrate(score) + 0.1, text)
        return result(None, score, 0.35, text)  # same CNIC, clearly different name: identity conflict, a person must look
    if best is None:
        return result(None, 0.0, 0.0)
    score, variant_only, initial_used, text, person = best
    conf = _calibrate(score)
    if cnic:  # a CNIC was given but is not 13 digits: do not trust it, and do not ignore it silently
        conf = min(conf, 0.7)
    if score < MATCH_MIN:
        return result(None, score, min(conf, 0.4), text)
    if len(scored) > 1 and scored[1][0] >= MATCH_MIN and rank(best) - rank(scored[1]) < AMBIGUOUS_GAP:
        return result(None, score, min(conf, 0.5), text)  # two people fit equally well: do not pick one
    corroborated, mismatched = extra[person.cnic]
    if variant_only:
        conf = min(conf, (VARIANT_CAP, 0.93, 0.95)[min(corroborated, 2)])
    if initial_used:
        conf = min(conf, INITIAL_CAP + (0.10 if corroborated >= 2 else 0.0))
    if mismatched:
        conf = min(conf, 0.5)  # the father's name or the date of birth disagrees: a person must look
    return result(person, score, conf, text)
