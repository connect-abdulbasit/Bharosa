"""Turn OCR text lines from an ID card into fields. Pure functions, no OCR engine needed (so they are tested with literal text).

parse(lines) -> (fields, scores): fields has only what was found and passes its own check:
  cnic           13 digits, dashes dropped (OCR digit confusions O/0, I/l/1, S/5, B/8 are repaired inside the digit run)
  name           the line after the "Name" label (or "Name: value" on one line)
  father_name    the line after "Father Name" / "Father/Husband Name"
  date_of_birth  YYYY-MM-DD from dd.mm.yyyy (or / or -), only a real date
Labels are matched loosely because OCR drops spaces and swaps letters ("ldentityNumber", "FatherName"). Nothing is guessed: a missing or
unreadable field is simply absent.
"""
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from bharosa_ai.matching import _dob

_LABELS: Dict[str, Tuple[str, ...]] = {
    "name": ("name",),
    "father_name": ("fathername", "husbandname", "fatherhusbandname", "fathershusbandname", "fatherorhusbandname"),
    "cnic": ("identitynumber", "cnic", "idnumber", "nicnumber", "cnicnumber", "identityno"),
    "date_of_birth": ("dateofbirth", "dob", "birthdate"),
    "other": ("gender", "countryofstay", "dateofissue", "dateofexpiry", "signature", "holderssignature", "sex"),
}
_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1", "S": "5", "s": "5", "B": "8", "b": "8", "Q": "0"})
_DIGITISH = "0-9OoIl|SsBbQ"
_CNIC = re.compile(r"(?<![0-9-])[%s]{5}-?[%s]{7}-?[%s](?![0-9-])" % (_DIGITISH, _DIGITISH, _DIGITISH))  # not inside a longer number
_SAME_LINE = re.compile(r"^\s*([A-Za-z/' ]{3,28}?)\s*[:\-]\s*(.+)$")


def _key(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower()).replace("l", "i")  # OCR confuses l and I


def _label(text: str) -> Optional[str]:
    key = _key(text)
    if len(key) < 3:
        return None
    for field, names in _LABELS.items():
        for n in names:
            if key == _key(n) or (len(key) >= 4 and SequenceMatcher(None, key, _key(n)).ratio() >= 0.88):
                return field
    return None


def cnic_from(text: str) -> Optional[str]:
    """A 13-digit CNIC found in the text, mostly digits (so a word is never read as a number), or None."""
    compact = re.sub(r"\s+", "", text)
    for m in _CNIC.finditer(compact):
        run = m.group().replace("-", "")
        digits = run.translate(_FIX)
        if digits.isdigit() and len(digits) == 13 and sum(c.isdigit() for c in run) >= 9:
            return digits
    return None


def _person(text: str) -> Optional[str]:
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", re.sub(r"[^A-Za-z' ]", " ", text))  # "AbdulRehman" -> "Abdul Rehman"
    s = re.sub(r"\s+", " ", s).strip()
    if not 2 <= len(s) <= 60 or _label(s) is not None:
        return None
    return s


def _date(text: str) -> Optional[str]:
    m = re.search(r"(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4})", text)
    return _dob("%s.%s.%s" % m.groups()) if m else None


def parse(lines: List[Tuple[str, float]]) -> Tuple[Dict[str, str], Dict[str, float]]:
    fields: Dict[str, str] = {}
    scores: Dict[str, float] = {}

    def put(field: str, value: Optional[str], score: float) -> None:
        if value and field not in fields:
            fields[field], scores[field] = value, float(score)

    for i, (text, score) in enumerate(lines or []):
        text = str(text or "")
        label, value, value_score = _label(text), None, score
        if label is None:
            m = _SAME_LINE.match(text)
            if m and _label(m.group(1)):
                label, value = _label(m.group(1)), m.group(2)
        elif i + 1 < len(lines) and _label(str(lines[i + 1][0])) is None:
            value, value_score = str(lines[i + 1][0]), min(score, float(lines[i + 1][1]))  # the value is on the next line
        if value is None:
            continue
        if label == "name":
            put("name", _person(value), value_score)
        elif label == "father_name":
            put("father_name", _person(value), value_score)
        elif label == "cnic":
            put("cnic", cnic_from(value), value_score)
        elif label == "date_of_birth":
            put("date_of_birth", _date(value), value_score)
    if "cnic" not in fields:  # the number is recognisable wherever it is printed
        for text, score in lines or []:
            found = cnic_from(str(text or ""))
            if found:
                put("cnic", found, score)
                break
    return fields, scores
