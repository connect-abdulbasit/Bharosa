"""The committed SPECIMEN cards (ai/data/sample_id_specimen*.jpg, all fake): quality gate always, OCR fields when an engine is installed
(the backend Docker image has Tesseract with the English + Urdu packs)."""
import os

import pytest

import bharosa_ai
from bharosa_ai import document, ocr

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def _bytes(name):
    with open(os.path.join(DATA, name), "rb") as f:
        return f.read()


def test_blurry_specimen_is_sent_for_retake_never_read():
    r = document.read_document(_bytes("sample_id_specimen_blurry.jpg"))
    assert r.blur_score >= 0.5 and r.confidence < 0.5 and r.fields == {}


def test_sharp_specimen_passes_the_quality_gate():
    r = document.read_document(_bytes("sample_id_specimen.jpg"))
    assert r.blur_score < 0.5 and r.format_ok is not None


def test_sharp_specimen_ocr_fields_when_an_engine_is_installed(monkeypatch):
    monkeypatch.setenv("AI_USE_OCR", "1")
    ocr._RUNNERS.clear()
    if not ocr.available():
        pytest.skip("no OCR engine installed here (the Docker image has Tesseract)")
    r = bharosa_ai.document.read_document(_bytes("sample_id_specimen.jpg"))
    assert r.fields.get("cnic") == "0000042101002" and r.fields.get("name") == "Fatima Noor"
