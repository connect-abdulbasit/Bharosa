"""ID photo processing: validate it really is an image, fix orientation, shrink to max 1280 px, re-encode as JPEG q80.
Re-encoding drops EXIF (GPS, camera, time) and keeps stored files small (max 2 MB) for weak connections and free databases."""
import io
from typing import Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

MAX_PIXELS = 50_000_000  # refuse decompression bombs before decoding


class ImageRejected(ValueError):
    pass


class ImageTooLarge(ValueError):
    pass


def _resample():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def process_image(data: bytes) -> Tuple[bytes, int, int]:
    """Returns (jpeg_bytes, width, height). Raises ImageRejected (not an image) or ImageTooLarge (cannot get under the cap)."""
    try:
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise ImageRejected("image has too many pixels")
        img.load()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageRejected("not a readable image: %s" % exc.__class__.__name__)
    img = ImageOps.exif_transpose(img)  # phones store rotation in EXIF: apply it, then the EXIF is dropped
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.split()[-1])
        img = flat
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    side = settings.DOCUMENT_MAX_SIDE
    img.thumbnail((side, side), _resample())  # only ever shrinks
    quality = settings.DOCUMENT_JPEG_QUALITY
    for _ in range(8):  # almost never needed: a 1280 px q80 JPEG is a few hundred KB
        out = io.BytesIO()
        img.save(out, "JPEG", quality=quality, optimize=True)
        if out.tell() <= settings.MAX_DOCUMENT_BYTES:
            return out.getvalue(), img.width, img.height
        if quality > 50:
            quality -= 10
        else:
            img = img.resize((max(int(img.width * 0.8), 64), max(int(img.height * 0.8), 64)), _resample())
    raise ImageTooLarge("image cannot be made smaller than %d bytes" % settings.MAX_DOCUMENT_BYTES)
