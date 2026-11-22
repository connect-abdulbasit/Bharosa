"""Spoken Urdu (and English) for read-aloud. Most phones and laptops have no Urdu voice, so the server makes the audio.

Only the sentence the person is already reading is sent to the voice service; nothing else (no ids, no names beyond what the sentence says).
Failure is never fatal: the caller answers 503 and the browser falls back to its own voice. TTS_PROVIDER=off disables it.
"""
import asyncio
import hashlib
import logging
from collections import OrderedDict
from typing import Optional

from app.config import settings

log = logging.getLogger("bharosa.tts")
VOICES = {"ur": "ur-PK-UzmaNeural", "en": "en-GB-SoniaNeural"}
MAX_CHARS = 600
_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_CACHE_MAX = 64  # same sentences (status messages) are asked for again and again


class TtsUnavailable(Exception):
    pass


async def _synthesize(text: str, voice: str) -> bytes:
    import edge_tts  # imported late: the app starts even if the package is missing

    out = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate="-10%").stream():  # a little slower for clarity
        if chunk["type"] == "audio":
            out.extend(chunk["data"])
    return bytes(out)


def speak(text: str, lang: str = "ur") -> bytes:
    """MP3 bytes for `text`. Raises TtsUnavailable when it is off or the service fails. Call from a worker thread (sync route)."""
    if settings.TTS_PROVIDER != "edge":
        raise TtsUnavailable("off")
    text = " ".join(text.split())[:MAX_CHARS]
    if not text:
        raise TtsUnavailable("empty")
    voice = VOICES.get(lang, VOICES["ur"])
    key = hashlib.sha256(("%s|%s" % (voice, text)).encode()).hexdigest()
    hit: Optional[bytes] = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit
    try:
        audio = asyncio.run(asyncio.wait_for(_synthesize(text, voice), settings.TTS_TIMEOUT_SECONDS))
    except Exception as exc:  # network, timeout, package missing: all the same to the caller
        log.warning("tts failed: %s", type(exc).__name__)
        raise TtsUnavailable(type(exc).__name__)
    if not audio:
        raise TtsUnavailable("no audio")
    _CACHE[key] = audio
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return audio
