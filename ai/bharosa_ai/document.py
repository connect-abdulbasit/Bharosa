"""read_document: quality gate for an ID-card photo, plus optional local OCR. Offline, never raises.

Quality gate (Pillow only): "can a person or a machine read this photo?". A blurry, dark, flat, tiny or undecodable photo is reported so
the citizen is asked to retake it.
Text extraction (optional, ocr.py + idcard.py): ONLY for a photo that passes the gate, and only when an OCR engine is installed (RapidOCR or
Tesseract; AI_USE_OCR=0 turns it off). The photo is read inside this process; nothing leaves it. Then `fields` holds what was read
(cnic, name, father_name, date_of_birth), a readable 13-digit CNIC is what makes `format_ok` true, and the confidence can reach 0.85
(never 0.90) when both the CNIC and the name were read. With no engine installed `fields` is empty and the confidence is capped at 0.75,
so a good photo never forces an officer by itself but can never auto-approve a claim on a card that nobody read.

blur_score is content-independent: how much of the fine detail disappears when the image is blurred once more. A sharp
photo loses most of it (ratio about 0.07), an already blurry one loses little (ratio 0.5 and up). Calibrated on the
synthetic cards of data/make_images.py: 0.5 is the retake line used by the backend (see _shared.BLUR_RETAKE).
"""
import io
from typing import Any, Dict

from PIL import Image, ImageFilter, ImageOps, ImageStat

from bharosa_ai import idcard, ocr
from contracts.ai_interface import DocumentReading

MODEL_VERSION = "doc-quality-1.0"
OCR_SIDE = 900         # the photo is shrunk to this before OCR (the backend already stores at most 1280 px)
OCR_CONF_MAX = 0.85    # with a CNIC and a name read; never the 0.90 auto line
MAX_PIXELS = 50_000_000   # refuse decompression bombs before decoding
WORK_SIDE = 640           # the blur metric is measured at this size
MIN_SIDE = 300            # smaller than this cannot hold a readable card
MAX_ASPECT = 3.0
CONF_MAX = 0.75
RATIO_SHARP, RATIO_SPAN = 0.10, 0.70   # blur_score = (ratio - RATIO_SHARP) / RATIO_SPAN, clamped to 0..1
BAD_EXPOSURE_BLUR = 0.8                # too dark, too bright or flat: treated as unreadable
_LAPLACIAN = ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)


def _unreadable() -> DocumentReading:
    return DocumentReading(fields={}, blur_score=1.0, format_ok=False, confidence=0.1, model_version=MODEL_VERSION)


def _detail(gray: Any) -> float:
    return float(ImageStat.Stat(gray.filter(_LAPLACIAN)).var[0])


def _confidence(blur: float, format_ok: bool) -> float:
    if blur <= 0.3:
        conf = CONF_MAX
    elif blur <= 0.5:
        conf = CONF_MAX - (blur - 0.3) * 0.75   # 0.75 down to 0.60: still readable, a little less sure
    else:
        conf = 0.6 - (blur - 0.5) * 0.8         # unusable photos: low
    return min(conf, 0.3) if not format_ok else conf


def read_document(image_bytes: bytes) -> DocumentReading:
    try:
        if not isinstance(image_bytes, (bytes, bytearray, memoryview)) or len(image_bytes) == 0:
            return _unreadable()
        img = Image.open(io.BytesIO(bytes(image_bytes)))
        if img.width * img.height > MAX_PIXELS:
            return _unreadable()
        img.load()
        gray = ImageOps.exif_transpose(img).convert("L")
        w, h = gray.size
        format_ok = min(w, h) >= MIN_SIDE and max(w, h) / max(min(w, h), 1) <= MAX_ASPECT
        gray.thumbnail((WORK_SIDE, WORK_SIDE))
        detail = _detail(gray)
        if detail < 5.0:  # almost no edges at all: a blank or flat picture
            blur = 1.0
        else:
            ratio = _detail(gray.filter(ImageFilter.GaussianBlur(1.5))) / detail
            blur = min(max((ratio - RATIO_SHARP) / RATIO_SPAN, 0.0), 1.0)
        stat = ImageStat.Stat(gray)
        if stat.mean[0] < 45 or stat.mean[0] > 225 or stat.stddev[0] < 25:  # too dark, washed out or no contrast
            blur = max(blur, BAD_EXPOSURE_BLUR)
        fields: Dict[str, str] = {}
        version, ocr_score = MODEL_VERSION, 0.0
        engine = ocr.engine_name() if blur <= 0.5 and format_ok else None  # only a photo that passed the gate is read
        if engine:
            rgb = ImageOps.exif_transpose(img).convert("RGB")
            rgb.thumbnail((OCR_SIDE, OCR_SIDE))
            lines = ocr.read_lines(rgb)
            if lines is not None:  # the engine ran (an engine failure returns None and leaves the quality-only result)
                fields, scores = idcard.parse(lines)
                version = "doc-ocr-%s-1.0" % engine
                format_ok = "cnic" in fields  # a readable 13-digit CNIC is what makes this a usable card photo
                if "cnic" in fields and "name" in fields:
                    ocr_score = (scores["cnic"] + scores["name"]) / 2
        confidence = _confidence(blur, format_ok)
        if "cnic" in fields and "name" in fields:
            confidence = min(OCR_CONF_MAX, confidence + 0.10 * ocr_score)
        return DocumentReading(fields=fields, blur_score=round(blur, 3), format_ok=format_ok, confidence=round(confidence, 3),
                               model_version=version)
    except Exception:  # not an image, truncated, bomb, or anything odd: report "unreadable", never raise
        return _unreadable()
