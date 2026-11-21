"""Local OCR for the ID photo: RapidOCR first (pip-only, no binary), Tesseract second (pytesseract plus the OS binary). Both optional.

The photo is read INSIDE this process: nothing is sent anywhere (no network, no vision LLM). Neither engine is a core dependency: install the
extra (`pip install "./ai[ocr]"`; Tesseract also needs its binary and, for Urdu, the `urd` language pack). With no engine, `available()` is
False and document.py keeps the quality-only behaviour. Never raises: any engine problem gives None.
Env: AI_USE_OCR=0 switches OCR off; AI_OCR_ENGINE=rapidocr|tesseract forces one engine.
"""
import os
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

ENGINES = ("rapidocr", "tesseract")
_LOCK = threading.Lock()  # the engines are not promised to be thread-safe: one photo at a time
_RUNNERS: Dict[str, Optional[Callable[[Any], List[Tuple[str, float]]]]] = {}


def _load_rapidocr() -> Optional[Callable[[Any], List[Tuple[str, float]]]]:
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR

        engine = RapidOCR()
    except Exception:
        return None

    def run(image: Any) -> List[Tuple[str, float]]:
        result, _ = engine(np.array(image.convert("RGB")), use_cls=False)  # cards are upright (EXIF already applied): skip the angle classifier
        rows = [(min(p[1] for p in box), min(p[0] for p in box), str(text), float(score)) for box, text, score in (result or [])]
        return [(text, score) for _, _, text, score in sorted(rows)]  # top to bottom, then left to right

    return run


def _tesseract_lang(pytesseract: Any) -> str:
    """English plus Urdu when both packs are installed (the Docker image has both), else English. AI_OCR_LANG overrides."""
    forced = os.environ.get("AI_OCR_LANG", "").strip()
    if forced:
        return forced
    try:
        have = set(pytesseract.get_languages(config=""))
    except Exception:
        return "eng"
    return "+".join(code for code in ("eng", "urd") if code in have) or "eng"


def _load_tesseract() -> Optional[Callable[[Any], List[Tuple[str, float]]]]:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()  # raises when the binary is not installed
    except Exception:
        return None

    def run(image: Any) -> List[Tuple[str, float]]:
        data = pytesseract.image_to_data(image.convert("L"), output_type=pytesseract.Output.DICT, config="--psm 6", lang=_tesseract_lang(pytesseract))
        lines: Dict[Tuple[int, int, int], List[Tuple[str, float]]] = {}
        for i, word in enumerate(data["text"]):
            if str(word).strip() and float(data["conf"][i]) >= 0:
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                lines.setdefault(key, []).append((str(word).strip(), float(data["conf"][i]) / 100.0))
        return [(" ".join(w for w, _ in ws), sum(s for _, s in ws) / len(ws)) for _, ws in sorted(lines.items())]

    return run


_LOADERS = {"rapidocr": _load_rapidocr, "tesseract": _load_tesseract}


def _runner(name: str) -> Optional[Callable[[Any], List[Tuple[str, float]]]]:
    with _LOCK:
        if name not in _RUNNERS:
            _RUNNERS[name] = _LOADERS[name]()  # loaded once: the model takes about a second to start
        return _RUNNERS[name]


def engine_name() -> Optional[str]:
    """The engine that will be used (the forced one, else the first installed), or None."""
    if os.environ.get("AI_USE_OCR", "1").strip() == "0":
        return None
    forced = os.environ.get("AI_OCR_ENGINE", "").strip().lower()
    for name in ((forced,) if forced in ENGINES else ENGINES):
        if _runner(name) is not None:
            return name
    return None


def available() -> bool:
    return engine_name() is not None


def read_lines(image: Any) -> Optional[List[Tuple[str, float]]]:
    """Text lines in reading order as (text, score 0..1) for a PIL image; [] when nothing was read; None when no engine ran."""
    name = engine_name()
    if name is None:
        return None
    try:
        runner = _runner(name)
        with _LOCK:
            return runner(image)  # type: ignore[misc]
    except Exception:
        return None
