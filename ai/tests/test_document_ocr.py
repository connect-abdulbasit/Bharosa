"""read_document() with OCR: the logic with a fake engine, and the real engine on generated fake cards (skipped when none is installed)."""
import importlib.util
from pathlib import Path

import pytest

from bharosa_ai import ocr
from bharosa_ai.document import read_document

_spec = importlib.util.spec_from_file_location("make_images_for_doc_ocr", Path(__file__).resolve().parents[1] / "data" / "make_images.py")
images = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(images)

CLEAN = [("IDENTITY CARD(FAKE)", 0.95), ("Name", 1.0), ("Muhammad Aslam", 1.0), ("Father Name", 0.96), ("Abdul Rehman", 0.99),
         ("Identity Number", 0.97), ("00000-4210100-1", 1.0), ("Date of Birth", 0.94), ("12.03.1984", 1.0)]


@pytest.fixture
def fake_ocr(monkeypatch):
    state = {"lines": CLEAN, "calls": 0, "engine": "fake"}

    def read_lines(image):
        state["calls"] += 1
        return state["lines"]

    monkeypatch.setattr(ocr, "engine_name", lambda: state["engine"])
    monkeypatch.setattr(ocr, "read_lines", read_lines)
    return state


def test_a_readable_card_fills_the_fields_and_raises_the_confidence_but_not_to_the_auto_line(fake_ocr):
    r = read_document(images.make_card(1))
    assert r.fields == {"name": "Muhammad Aslam", "father_name": "Abdul Rehman", "cnic": "0000042101001", "date_of_birth": "1984-03-12"}
    assert r.format_ok and 0.84 <= r.confidence <= 0.85 < 0.90 and r.model_version == "doc-ocr-fake-1.0" and len(r.model_version) <= 40
    assert fake_ocr["calls"] == 1


def test_a_photo_without_a_readable_cnic_must_be_retaken(fake_ocr):
    fake_ocr["lines"] = [("Name", 1.0), ("Muhammad Aslam", 1.0), ("Identity Number", 0.9), ("0000O-42", 0.8)]
    r = read_document(images.make_card(1))
    assert r.format_ok is False and r.confidence <= 0.3 and r.fields == {"name": "Muhammad Aslam"}


def test_a_cnic_without_a_name_keeps_the_quality_only_confidence(fake_ocr):
    fake_ocr["lines"] = [("Identity Number", 0.97), ("00000-4210100-1", 1.0)]
    r = read_document(images.make_card(1))
    assert r.format_ok and r.fields == {"cnic": "0000042101001"} and r.confidence == 0.75


def test_a_card_where_nothing_was_read_must_be_retaken(fake_ocr):
    fake_ocr["lines"] = []
    r = read_document(images.make_card(1))
    assert r.format_ok is False and r.fields == {} and r.confidence <= 0.3 and r.model_version == "doc-ocr-fake-1.0"


def test_an_engine_failure_leaves_the_quality_only_result(fake_ocr):
    fake_ocr["lines"] = None
    r = read_document(images.make_card(1))
    assert r.fields == {} and r.format_ok and r.confidence == 0.75 and r.model_version == "doc-quality-1.0"


@pytest.mark.parametrize("data", [images.make_card(1, blur=4.0), images.make_card(1, brightness=0.15), images.make_card(1, width=200, height=126)],
                         ids=["blurry", "dark", "too small"])
def test_a_photo_that_fails_the_quality_gate_is_not_read(fake_ocr, data):
    r = read_document(data)
    assert fake_ocr["calls"] == 0 and r.fields == {} and r.model_version == "doc-quality-1.0"


def test_without_an_engine_nothing_changes(fake_ocr):
    fake_ocr["engine"] = None
    r = read_document(images.make_card(1))
    assert fake_ocr["calls"] == 0 and r.fields == {} and r.format_ok and r.confidence == 0.75 and r.model_version == "doc-quality-1.0"


def test_the_photo_is_shrunk_before_it_goes_to_the_engine(monkeypatch):
    seen = []
    monkeypatch.setattr(ocr, "engine_name", lambda: "fake")
    monkeypatch.setattr(ocr, "read_lines", lambda image: seen.append(image.size) or CLEAN)
    read_document(images.make_card(1, width=2400, height=1500))
    assert seen and max(seen[0]) <= 900


def test_the_result_holds_only_strings_never_image_data(fake_ocr):
    r = read_document(images.make_card(1))
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in r.fields.items())
    assert not any(isinstance(v, (bytes, bytearray)) for v in r.model_dump().values())


@pytest.fixture
def real_engine(monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.setenv("AI_OCR_ENGINE", "rapidocr")
    monkeypatch.setattr(ocr, "_RUNNERS", {})


def test_the_real_engine_reads_a_generated_card(real_engine):
    r = read_document(images.make_cnic_card(1))
    assert r.fields == {"name": "Muhammad Aslam", "father_name": "Abdul Rehman", "cnic": "0000042101001", "date_of_birth": "1984-03-12"}
    assert r.format_ok and 0.80 <= r.confidence <= 0.85 and r.model_version == "doc-ocr-rapidocr-1.0"


def test_the_real_engine_reads_a_second_person_and_a_slightly_soft_photo(real_engine):
    r = read_document(images.make_cnic_card(2, name="Fatima Noor", father="Noor Muhammad", cnic="00000-4210100-2", dob="01.07.1979", gender="F", blur=1.5))
    assert r.fields["cnic"] == "0000042101002" and r.fields["name"] == "Fatima Noor" and r.format_ok


def test_a_blurry_photo_is_not_read_even_with_a_real_engine(real_engine):
    r = read_document(images.make_cnic_card(1, blur=5.0))
    assert r.blur_score > 0.5 and r.fields == {} and r.model_version == "doc-quality-1.0"
