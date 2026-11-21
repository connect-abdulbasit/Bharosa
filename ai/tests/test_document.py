"""Real read_document(): photo-quality gate on generated fake cards. No OCR: fields stay empty, confidence is capped."""
import importlib
import io
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

import bharosa_ai
from contracts.ai_interface import DocumentReading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
from make_images import make_card  # noqa: E402

_saved = (bharosa_ai.decide, bharosa_ai.explain)
_m = importlib.import_module("bharosa_ai.document")
bharosa_ai.decide, bharosa_ai.explain = _saved
read_document = _m.read_document
BLUR_RETAKE = importlib.import_module("bharosa_ai._shared").BLUR_RETAKE


def _png(img):
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_sharp_card_is_clear_and_gets_the_capped_confidence():
    r = read_document(make_card(1))
    assert isinstance(r, DocumentReading)
    assert r.blur_score < 0.2 and r.format_ok and r.confidence == 0.75 and r.fields == {}
    assert r.model_version == "doc-quality-1.0"


def test_slightly_soft_card_is_still_usable_and_never_forces_an_officer():
    r = read_document(make_card(1, blur=1.6))
    assert 0.2 < r.blur_score <= BLUR_RETAKE and r.format_ok and r.confidence >= 0.6


@pytest.mark.parametrize("radius", [2.6, 3.0, 4.0, 6.0])
def test_blurry_card_must_be_retaken(radius):
    r = read_document(make_card(1, blur=radius))
    assert r.blur_score > BLUR_RETAKE and r.confidence < 0.6


def test_blur_score_never_decreases_as_the_blur_grows():
    scores = [read_document(make_card(2, blur=b)).blur_score for b in (0, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 6.0)]
    assert scores == sorted(scores)


@pytest.mark.parametrize("kwargs", [{"brightness": 0.15}, {"contrast": 0.2}, {"brightness": 3.0}])
def test_too_dark_washed_out_or_flat_is_unreadable(kwargs):
    assert read_document(make_card(1, **kwargs)).blur_score >= 0.8


def test_flat_picture_is_unreadable():
    out = io.BytesIO()
    Image.new("L", (640, 400), 128).save(out, "JPEG")
    r = read_document(out.getvalue())
    assert r.blur_score == 1.0 and r.confidence < 0.6


def test_tiny_or_extreme_shapes_are_not_a_card_photo():
    small = read_document(make_card(1, width=200, height=126))
    assert small.format_ok is False and small.confidence <= 0.3
    strip = read_document(make_card(1, width=1500, height=100))
    assert strip.format_ok is False


@pytest.mark.parametrize("data", [b"", b"garbage", b"x" * 5000, "not bytes", None, 123, b"\xff\xd8\xff\xe0" + b"\x00" * 50])
def test_not_an_image_is_unreadable_not_an_exception(data):
    r = read_document(data)  # type: ignore[arg-type]
    assert (r.format_ok, r.blur_score, r.confidence, r.fields) == (False, 1.0, 0.1, {})


def test_truncated_jpeg_is_unreadable():
    data = make_card(1)
    assert read_document(data[: len(data) // 3]).format_ok is False


def test_other_formats_and_modes_work():
    base = Image.open(io.BytesIO(make_card(1)))
    assert read_document(_png(base)).format_ok
    assert read_document(_png(base.convert("RGBA"))).format_ok
    assert read_document(_png(base.convert("P"))).format_ok
    assert read_document(bytearray(make_card(1))).format_ok


def test_rotated_photo_keeps_its_score():
    a, b = read_document(make_card(1)), read_document(make_card(1, rotate=90))
    assert abs(a.blur_score - b.blur_score) < 0.15 and b.format_ok


def test_backend_noise_test_image_does_not_crash():
    out = io.BytesIO()
    Image.effect_noise((600, 400), 60).save(out, "JPEG")
    r = read_document(out.getvalue())
    assert r.format_ok and 0.0 <= r.blur_score <= 1.0


@pytest.mark.filterwarnings("ignore:Image size:PIL.Image.DecompressionBombWarning")
def test_decompression_bomb_is_refused_cheaply():
    r = read_document(_png(Image.new("1", (10000, 10000))))
    assert r.format_ok is False and r.blur_score == 1.0


def test_large_photo_is_fast():
    data = make_card(1, width=3000, height=1900)
    start = time.time()
    r = read_document(data)
    assert r.format_ok and time.time() - start < 3


def test_output_holds_no_image_data_and_is_deterministic():
    data = make_card(1, blur=1.0)
    a = read_document(data)
    assert a.model_dump() == read_document(data).model_dump()
    assert all(not isinstance(v, (bytes, bytearray)) for v in a.model_dump().values())
