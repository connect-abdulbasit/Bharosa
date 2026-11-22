from app.config import settings
from app.services import tts
from tests.conftest import auth


def _fake(monkeypatch, audio=b"ID3fake"):
    calls = []

    async def fake(text, voice):
        calls.append((text, voice))
        return audio

    monkeypatch.setattr(tts, "_synthesize", fake)
    monkeypatch.setattr(settings, "TTS_PROVIDER", "edge")
    tts._CACHE.clear()
    return calls


def test_urdu_audio_and_cache(client, monkeypatch):
    calls = _fake(monkeypatch)
    h = auth(client, "citizen")
    r = client.post("/tts", json={"text": "آپ کا کیس افسر کو بھیج دیا گیا ہے۔"}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake"
    assert calls[0][1] == "ur-PK-UzmaNeural"
    client.post("/tts", json={"text": "آپ کا کیس افسر کو بھیج دیا گیا ہے۔"}, headers=h)
    assert len(calls) == 1  # second call comes from the cache


def test_roles_and_validation(client, monkeypatch):
    _fake(monkeypatch)
    assert client.post("/tts", json={"text": "x"}).status_code == 401
    assert client.post("/tts", json={"text": "x"}, headers=auth(client, "auditor")).status_code == 403
    assert client.post("/tts", json={"text": ""}, headers=auth(client, "citizen")).status_code == 422
    assert client.post("/tts", json={"text": "x" * 601}, headers=auth(client, "citizen")).status_code == 422
    assert client.post("/tts", json={"text": "x", "lang": "fr"}, headers=auth(client, "citizen")).status_code == 422


def test_failure_and_off_answer_503_not_500(client, monkeypatch):
    _fake(monkeypatch)

    async def boom(text, voice):
        raise RuntimeError("network down")

    monkeypatch.setattr(tts, "_synthesize", boom)
    assert client.post("/tts", json={"text": "salam"}, headers=auth(client, "citizen")).status_code == 503
    monkeypatch.setattr(settings, "TTS_PROVIDER", "off")
    assert client.post("/tts", json={"text": "salam"}, headers=auth(client, "citizen")).status_code == 503
