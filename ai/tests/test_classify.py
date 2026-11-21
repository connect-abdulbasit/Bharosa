"""Real classify_message(): English, Roman Urdu and Urdu messages, look-alike senders, warnings, thin evidence, hostile input."""
import importlib
import time

import pytest

import bharosa_ai
from contracts.enums import MessageLabel

_saved = (bharosa_ai.decide, bharosa_ai.explain)
_m = importlib.import_module("bharosa_ai.classify")
bharosa_ai.decide, bharosa_ai.explain = _saved
classify_message = _m.classify_message

SCAM, GENUINE, UNSURE = MessageLabel.scam, MessageLabel.genuine, MessageLabel.unsure

CASES = [
    # --- scam: English
    ("Pay fee at http://bit.ly/x to get relief", "SAHARA-INFO", SCAM),
    ("Congratulations! You have won a relief bonus. Send Rs 500 processing fee to JazzCash 0300-0000000 urgently", "0300-0000000", SCAM),
    ("Your stipend is ready. Click here to verify your account", "9O9O", SCAM),            # look-alike sender
    ("Your relief payment is suspended. Share your OTP and CNIC number immediately", "RELIEF-PAY", SCAM),
    # --- scam: Roman Urdu
    ("Aap ka relief payment block ho jaye ga. Fori apna OTP aur CNIC number batain", "RELIEF-PAY", SCAM),
    ("Fees jama karwa den warna payment cancel ho jaye gi http://tinyurl.com/abc", "03001234567", SCAM),
    # --- scam: Urdu script
    ("آپ کی امدادی رقم روک دی گئی ہے۔ فوری فیس جمع کروائیں ورنہ اکاؤنٹ بلاک", "GOV-RELIEF", SCAM),
    ("مبارک ہو! آپ نے انعام جیتا ہے۔ ابھی لنک پر کلک کریں http://bit.ly/z", "SAHARA-lNFO", SCAM),
    # --- genuine: official code, nothing suspicious
    ("Your stipend is ready", "9090", GENUINE),
    ("Your October stipend of PKR 12000 has been credited. Never share your PIN or OTP with anyone.", "9090", GENUINE),
    ("آپ کا وظیفہ جاری کر دیا گیا ہے", "9090", GENUINE),
    ("Aap ki ada'igi bhej di gayi hai. Koi fees nahi hai.", "9090", GENUINE),
    ("Your payment is ready. Never pay any fee to anyone", "9090", GENUINE),             # a warning, not a request
    ("Apna PIN ya OTP kisi ko na batain", "9090", GENUINE),
    ("آپ کی رقم 12000 روپے جمع کر دی گئی ہے", "9090", GENUINE),                       # "has been deposited", not "deposit!"
    ("Aap ki raqam jama kar di gayi hai", "9090", GENUINE),
    # --- unsure: thin or mixed evidence
    ("Please call the office for details", "SAHARA-HELP", UNSURE),
    ("Your payment status has changed", "0300-1111111", UNSURE),
    ("hello", "", UNSURE),
    ("Check your status at http://example.pk", "SAHARA-INFO", UNSURE),          # a link alone is not proof
    ("Your stipend is ready. Pay the fee to receive it", "9090", UNSURE),       # official code but a warning sign
    ("Your stipend is ready", "9091", UNSURE),                                  # not 9090: content alone cannot confirm it
]


@pytest.mark.parametrize("text,sender,expected", CASES)
def test_labels(text, sender, expected):
    v = classify_message(text, sender)
    assert v.label == expected, (v.label, v.confidence, v.reasons)
    assert v.reasons and v.model_version == "classify-rules-1.0"


@pytest.mark.parametrize("text", [
    "Beware of fake messages asking for fees or OTP. The official code is 9090 only",
    "We will never ask you for money, a PIN or an OTP. Report anyone who does",
    "Jaali paighaam se hoshiyar rahein jo fees ya OTP mangte hain. Sarkari code sirf 9090 hai",
    "جعلی پیغامات سے ہوشیار رہیں جو فیس یا او ٹی پی مانگتے ہیں۔ سرکاری کوڈ صرف 9090 ہے",
])
def test_an_official_warning_about_fees_and_otps_is_not_a_scam(text):
    assert classify_message(text, "9090").label == GENUINE   # mentioning a fee or an OTP in order to warn is not asking for one


@pytest.mark.parametrize("text,sender", [
    ("Beware of fake messages. Pay the fee at http://bit.ly/x now", "SAHARA-INFO"),     # the warning is a different sentence
    ("Beware fake offers, pay fee now http://bit.ly/x", "RELIEF-PAY"),                  # same sentence: the link and sender still give it away
    ("Never mind the others, send your OTP now", "0300-1112233"),                       # "never" is no warning word
])
def test_a_scammer_cannot_hide_behind_a_warning_word(text, sender):
    assert classify_message(text, sender).label == SCAM


@pytest.mark.parametrize("text,sender", [
    ("Verification failed. Re-verify now at www.sahara-bio.net", "SAHARA-BIO"),
    ("Congratulations, you won PKR 100000. Call 0311-2223344 to claim", "LUCKY-DRAW"),
    ("لنک پر جا کر تصدیق کریں www.sahara-check.com", "SAHARA-CHECK"),
    ("Reply with your account number to receive your relief amount", "0300-7776666"),
])
def test_more_scam_patterns_are_caught(text, sender):
    assert classify_message(text, sender).label == SCAM


def test_confidence_ranges_match_the_label():
    for text, sender, _ in CASES:
        v = classify_message(text, sender)
        if v.label == SCAM:
            assert 0.5 <= v.confidence <= 0.99
        elif v.label == GENUINE:
            assert 0.85 <= v.confidence <= 0.95
        else:
            assert 0.4 <= v.confidence <= 0.6


def test_lookalike_sender_is_named_in_the_reasons():
    v = classify_message("Your stipend is ready", "9O9O")
    assert v.label == SCAM and any("looks like the official code" in r for r in v.reasons)
    assert classify_message("Your stipend is ready", "9o9o").label == SCAM


def test_a_warning_is_not_a_scam_cue_but_a_request_is():
    warn = classify_message("Never share your PIN with anyone", "9090")
    ask = classify_message("Send your PIN now", "9090")
    assert warn.label == GENUINE and ask.label != GENUINE


def test_no_fee_statement_is_not_a_fee_request():
    assert classify_message("There is no fee for this payment", "9090").label == GENUINE


def test_obfuscated_repeats_and_arabic_digits_are_normalised():
    assert classify_message("pay the feeeeees at http://bit.ly/١٢", "X-INFO").label == SCAM


def test_stub_messages_keep_their_labels():
    assert classify_message("Pay fee at http://bit.ly/x to get relief", "SAHARA-INFO").label == SCAM
    assert classify_message("Your stipend is ready", "9090").label == GENUINE


@pytest.mark.parametrize("text,sender", [("", ""), (None, None), ("x" * 10000, "9090"), ("\x00�​", "​"), (123, 456),
                                         ("a" * 200000, "s" * 1000)])
def test_never_raises_on_odd_input(text, sender):
    v = classify_message(text, sender)  # type: ignore[arg-type]
    assert v.label in (SCAM, GENUINE, UNSURE) and 0.0 <= v.confidence <= 1.0


def test_is_fast_on_long_input():
    start = time.time()
    classify_message("pay fee " * 5000, "9090")
    assert time.time() - start < 1.0


def test_deterministic():
    a = classify_message("Pay fee at http://bit.ly/x", "SAHARA-INFO")
    assert a.model_dump() == classify_message("Pay fee at http://bit.ly/x", "SAHARA-INFO").model_dump()
