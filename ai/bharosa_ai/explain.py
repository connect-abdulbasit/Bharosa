"""explain: plain-language Urdu or English text from a decision trace. Deterministic templates, offline, never raises.

Written to be read aloud: short sentences, numbers as digits, "rupees" spelled out. Facts come only from known trace keys
(action, flags, needs, shortfall, payment_needed, failed_step, hard_stops, capped_by); free text from the trace is never
copied into the output.
The backend appends "We need: <needs>." to the ENGLISH text itself, so the English here never lists the needs. The backend
appends nothing to Urdu, so known needs are written out in Urdu here.
"""
from typing import Any, Dict, List, Optional

from contracts.enums import DecisionAction


_HEADLINE = {
    "auto_handle": ("Your request looks correct and is moving forward.", "آپ کی درخواست درست لگتی ہے اور آگے بڑھ رہی ہے۔"),
    "ask_more": ("Thank you. A little more proof is needed before we can go on.", "شکریہ۔ آگے بڑھنے سے پہلے تھوڑا اور ثبوت چاہیے۔"),
    "send_to_human": ("We have sent your case to an officer, who will contact you.", "ہم نے آپ کا کیس افسر کو بھیج دیا ہے۔ وہ آپ سے رابطہ کریں گے۔"),
}
_PAYMENT = ("Any payment must be approved by an officer first.", "کوئی بھی ادائیگی پہلے افسر کی منظوری سے ہوگی۔")
_PHOTO = ("Please send a clear photo of your ID card.", "براہ کرم شناختی کارڈ کی صاف تصویر بھیجیں۔")
_FLAGS = {
    "duplicate_payment": ("Our records show the same payment twice, so an officer will check it.",
                          "ہمارے ریکارڈ میں ایک ہی ادائیگی دو بار درج ہے، اس لیے افسر اسے دیکھے گا۔"),
    "duplicate_claim": ("You already have an open claim for this month, so we are not opening a second one.",
                        "اس مہینے کے لیے آپ کا ایک دعویٰ پہلے سے کھلا ہے، اس لیے دوسرا نہیں کھولا جا رہا۔"),
    "claim_contradicts_ledger": ("Our records and your claim do not agree, so an officer will look at it carefully.",
                                 "ہمارے ریکارڈ اور آپ کے دعوے میں فرق ہے، اس لیے افسر اسے غور سے دیکھے گا۔"),
    "name_not_matched": ("The name you gave does not match our record, so an officer will check.",
                         "آپ کا بتایا ہوا نام ہمارے ریکارڈ سے نہیں ملتا، اس لیے افسر دیکھے گا۔"),
    "mock_service_failure": ("One of our checks could not be finished. Nothing is lost.",
                             "ہماری ایک جانچ مکمل نہیں ہو سکی۔ کچھ ضائع نہیں ہوا۔"),
    "document_mismatch": ("The ID number on the card photo does not match the one you gave, so an officer will check.",
                          "کارڈ کی تصویر پر شناختی نمبر آپ کے بتائے ہوئے نمبر سے نہیں ملتا، اس لیے افسر دیکھے گا۔"),
    "document_name_mismatch": ("The name on the ID card does not match the name you gave, so an officer will check.",
                               "کارڈ پر لکھا نام آپ کے بتائے ہوئے نام سے نہیں ملتا، اس لیے افسر دیکھے گا۔"),
}
_SHORT = ("Our records show you were paid less than the full amount.", "ہمارے ریکارڈ کے مطابق آپ کو پوری رقم نہیں ملی۔")
_DUE = ("%d rupees is still due.", "%d روپے باقی ہیں۔")
_UNCLEAR_PHOTO = ("The ID card photo was not clear.", "شناختی کارڈ کی تصویر صاف نہیں تھی۔")
_STEPS = {
    "identity_lookup": ("identity check", "شناخت کی جانچ"), "ledger_lookup": ("payment check", "ادائیگی کی جانچ"),
    "extract_claim": ("step that reads your claim", "آپ کا دعویٰ سمجھنے کا مرحلہ"), "read_document": ("ID photo check", "کارڈ کی تصویر کی جانچ"),
    "match_person": ("name check", "نام کی جانچ"), "notify": ("text message update", "پیغام بھیجنے کا مرحلہ"),
}
# known "needs" (English text made by the backend) -> Urdu sentence, matched by keyword
_NEEDS_UR = [
    (("retake", "blurry"), "براہ کرم روشنی میں کارڈ سیدھا رکھ کر شناختی کارڈ کی تصویر دوبارہ لیں۔"),
    (("upload the id",), "براہ کرم شناختی کارڈ کی تصویر دوبارہ بھیجیں۔"),
    (("problem again",), "براہ کرم اپنا مسئلہ دوبارہ، آہستہ اور صاف بتائیں۔"),
    (("photo", "id card"), "براہ کرم شناختی کارڈ کی صاف تصویر بھیجیں۔"),
    (("more details",), "براہ کرم گمشدہ رقم کے بارے میں مزید تفصیل بتائیں: آپ کو کب ملنی تھی اور عام طور پر کون دیتا ہے۔"),
]


def _list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    return [v for v in value if isinstance(v, str)] if isinstance(value, (list, tuple)) else []


def _amount(value: Any) -> Optional[int]:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def explain(trace: Dict[str, Any], lang: str) -> str:
    ur = str(lang).lower() == "ur"
    pick = (lambda pair: pair[1]) if ur else (lambda pair: pair[0])
    try:
        return _explain(trace if isinstance(trace, dict) else {}, ur, pick)
    except Exception:  # an explanation must never break a case
        return pick(_HEADLINE["send_to_human"])


def _explain(trace: Dict[str, Any], ur: bool, pick) -> str:
    action = trace.get("action")
    action = action if action in _HEADLINE else DecisionAction.send_to_human.value
    flags = _list(trace.get("flags")) + _list(trace.get("red_flags")) + _list(trace.get("flags_found")) + _list(trace.get("hard_stops"))
    needs = [n.lower() for n in _list(trace.get("needs"))]
    failed = trace.get("failed_step") if isinstance(trace.get("failed_step"), str) else None
    paying = bool(trace.get("payment_needed") or trace.get("payment_step"))
    out = [pick(_HEADLINE[action])]

    if failed:
        step = pick(_STEPS.get(failed, ("check", "جانچ")))
        out.append("آپ کا کیس %s پر رکا ہوا ہے۔ کچھ ضائع نہیں ہوا، افسر اسے آگے بڑھائے گا۔" % step if ur else
                   "Your case is paused at the %s. Nothing is lost, and an officer will continue it." % step)
        flags = [f for f in flags if f != "mock_service_failure"]
    if trace.get("capped_by") == "document_unclear":
        out.append(pick(_UNCLEAR_PHOTO))
    if "short_payment" in flags:
        short = _amount(trace.get("shortfall"))
        out.append(pick(_SHORT) + ((" " + pick(_DUE) % short) if short else ""))
    for flag in dict.fromkeys(flags):
        if flag in _FLAGS and len(out) < 4:
            out.append(pick(_FLAGS[flag]))

    if action == "ask_more":
        if ur:
            lines = [next((line for keys, line in _NEEDS_UR if any(k in n for k in keys)), None) for n in needs]
            out.extend(dict.fromkeys(line for line in lines if line) or [_PHOTO[1]])
        elif not needs:
            out.append(_PHOTO[0])  # nothing specific was given, so name the usual missing piece
    if paying:
        out.append(pick(_PAYMENT))
    return " ".join(out)
