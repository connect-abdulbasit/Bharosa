from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.auth import require_role
from app.models import User
from app.routing import CompactRoute
from app.services import tts
from contracts.enums import Role

router = APIRouter(tags=["tts"], route_class=CompactRoute)


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts.MAX_CHARS)
    lang: str = Field(default="ur", pattern="^(ur|en)$")


@router.post("/tts", summary="Spoken audio (MP3) for a sentence, Urdu by default",
             responses={200: {"content": {"audio/mpeg": {}}}, 503: {"description": "Voice service unavailable: use the browser voice"}})
def speak(body: SpeakRequest, user: User = Depends(require_role(Role.citizen, Role.helper, Role.officer, Role.admin))):
    """Used by read-aloud when the device has no Urdu voice. Not audited: it changes nothing and stores nothing."""
    try:
        audio = tts.speak(body.text, body.lang)
    except tts.TtsUnavailable:
        raise HTTPException(status_code=503, detail="The voice service is not available right now. Your device voice will be used.")
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})
