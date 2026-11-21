"""ocr.py: the engine adapter. Logic is tested with fake engines; one real RapidOCR test is skipped when it is not installed."""
import sys
import types

import pytest
from PIL import Image

from bharosa_ai import ocr

IMG = Image.new("RGB", (40, 20), "white")


@pytest.fixture
def both(monkeypatch):
    """Both engines 'installed' as fake runners."""
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.delenv("AI_OCR_ENGINE", raising=False)
    runners = {"rapidocr": lambda image: [("from rapid", 0.9)], "tesseract": lambda image: [("from tesseract", 0.8)]}
    monkeypatch.setattr(ocr, "_runner", lambda name: runners.get(name))
    return runners


def test_rapidocr_is_preferred_and_tesseract_is_the_fallback(both, monkeypatch):
    assert ocr.engine_name() == "rapidocr" and ocr.available() and ocr.read_lines(IMG) == [("from rapid", 0.9)]
    both["rapidocr"] = None
    monkeypatch.setattr(ocr, "_runner", lambda name: both.get(name))
    assert ocr.engine_name() == "tesseract" and ocr.read_lines(IMG) == [("from tesseract", 0.8)]


def test_an_engine_can_be_forced(both, monkeypatch):
    monkeypatch.setenv("AI_OCR_ENGINE", "tesseract")
    assert ocr.engine_name() == "tesseract"
    monkeypatch.setenv("AI_OCR_ENGINE", "RapidOCR")
    assert ocr.engine_name() == "rapidocr"
    monkeypatch.setenv("AI_OCR_ENGINE", "nonsense")
    assert ocr.engine_name() == "rapidocr"                       # an unknown name falls back to the normal order


def test_a_forced_engine_that_is_not_installed_means_no_ocr(both, monkeypatch):
    both["tesseract"] = None
    monkeypatch.setattr(ocr, "_runner", lambda name: both.get(name))
    monkeypatch.setenv("AI_OCR_ENGINE", "tesseract")
    assert ocr.engine_name() is None and ocr.read_lines(IMG) is None


def test_the_kill_switch_means_no_ocr_and_no_engine_is_started(monkeypatch):
    started = []
    monkeypatch.setattr(ocr, "_runner", lambda name: started.append(name))
    monkeypatch.setenv("AI_USE_OCR", "0")
    assert ocr.engine_name() is None and not ocr.available() and ocr.read_lines(IMG) is None and started == []


def test_no_engine_installed_means_none(monkeypatch):
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.setattr(ocr, "_runner", lambda name: None)
    assert ocr.engine_name() is None and ocr.read_lines(IMG) is None


def test_an_empty_read_is_not_a_failure_and_an_engine_error_is_not_an_exception(both, monkeypatch):
    both["rapidocr"] = lambda image: []
    monkeypatch.setattr(ocr, "_runner", lambda name: both.get(name))
    assert ocr.read_lines(IMG) == []                              # the engine ran and found no text
    def boom(image):
        raise RuntimeError("model crashed")
    both["rapidocr"] = boom
    monkeypatch.setattr(ocr, "_runner", lambda name: both.get(name))
    assert ocr.read_lines(IMG) is None                            # the engine failed: the caller keeps the quality-only result


def test_an_engine_is_loaded_once(monkeypatch):
    loads = []
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.setattr(ocr, "_RUNNERS", {})
    monkeypatch.setattr(ocr, "_LOADERS", {"rapidocr": lambda: loads.append(1) or (lambda image: []), "tesseract": lambda: None})
    ocr.read_lines(IMG)
    ocr.read_lines(IMG)
    assert loads == [1]


def test_the_tesseract_runner_groups_words_into_lines(monkeypatch):
    data = {"text": ["Name", "", "Muhammad", "Aslam", "noise"], "conf": ["96", "-1", "90", "80", "-1"],
            "block_num": [1, 1, 1, 1, 1], "par_num": [1, 1, 1, 1, 1], "line_num": [1, 1, 2, 2, 3]}
    fake = types.SimpleNamespace(Output=types.SimpleNamespace(DICT="dict"), get_tesseract_version=lambda: "5.3",
                                 image_to_data=lambda image, output_type, config: data)
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    run = ocr._load_tesseract()
    assert run(IMG) == [("Name", 0.96), ("Muhammad Aslam", pytest.approx(0.85))]


def test_a_missing_tesseract_binary_means_the_engine_is_unavailable(monkeypatch):
    def no_binary():
        raise RuntimeError("tesseract is not installed")

    monkeypatch.setitem(sys.modules, "pytesseract", types.SimpleNamespace(get_tesseract_version=no_binary))
    assert ocr._load_tesseract() is None


def test_the_rapidocr_runner_reads_in_reading_order_without_the_angle_classifier(monkeypatch):
    np = pytest.importorskip("numpy")
    calls = []

    class FakeRapidOCR:
        def __call__(self, array, use_cls=True):
            calls.append((array.shape, use_cls))
            box = lambda x, y: [[x, y], [x + 50, y], [x + 50, y + 20], [x, y + 20]]  # noqa: E731
            return [[box(300, 200), "third", 0.7], [box(10, 100), "second left", 0.8], [box(200, 100), "second right", 0.9], [box(10, 10), "first", 1.0]], None

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", types.SimpleNamespace(RapidOCR=FakeRapidOCR))
    run = ocr._load_rapidocr()
    assert [t for t, _ in run(IMG)] == ["first", "second left", "second right", "third"]
    assert calls == [((20, 40, 3), False)] and np is not None


def test_a_missing_engine_package_means_the_engine_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)  # makes the import fail
    assert ocr._load_rapidocr() is None


def test_the_real_rapidocr_engine_reads_a_generated_card(monkeypatch):
    pytest.importorskip("rapidocr_onnxruntime")
    import importlib.util
    from pathlib import Path
    import io

    spec = importlib.util.spec_from_file_location("make_images_for_ocr", Path(__file__).resolve().parents[1] / "data" / "make_images.py")
    maker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(maker)
    monkeypatch.setenv("AI_USE_OCR", "1")
    monkeypatch.setenv("AI_OCR_ENGINE", "rapidocr")
    monkeypatch.setattr(ocr, "_RUNNERS", {})
    assert ocr.engine_name() == "rapidocr"
    lines = ocr.read_lines(Image.open(io.BytesIO(maker.make_cnic_card(1))))
    texts = [t for t, _ in lines]
    assert "00000-4210100-1" in texts and "Muhammad Aslam" in texts and all(0.0 <= s <= 1.0 for _, s in lines)
