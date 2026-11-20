"""ID photo upload. Stored locally (UPLOAD_DIR), read by the AI (OCR + blur check), linked to a claim later."""
import uuid
from typing import Optional

import bharosa_ai as ai
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_role
from app.config import settings
from app.db import get_db
from app.models import Document, User
from app.services import audit
from app.services.access import resolve_citizen
from contracts.enums import Role
from contracts.schemas import DocumentResponse

router = APIRouter(tags=["documents"])
MAGIC = [(b"\x89PNG\r\n\x1a\n", ".png"), (b"\xff\xd8\xff", ".jpg"), (b"RIFF", ".webp")]
BLUR_RETAKE = 0.5


def sniff_extension(data: bytes) -> Optional[str]:
    for magic, ext in MAGIC:
        if data.startswith(magic) and (ext != ".webp" or data[8:12] == b"WEBP"):
            return ext
    return None


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), kind: str = Form("id_card"), citizen_id: Optional[str] = Form(None),
                          user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """Helpers must name the citizen (and pass the family link check)."""
    cid = resolve_citizen(db, user, citizen_id)
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max %d MB)" % (settings.MAX_UPLOAD_BYTES // (1024 * 1024)))
    ext = sniff_extension(data)
    if ext is None:
        raise HTTPException(status_code=415, detail="Please upload a PNG, JPEG or WebP photo")
    doc_id = str(uuid.uuid4())
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = doc_id + ext
    (settings.UPLOAD_DIR / name).write_bytes(data)

    reading = ai.read_document(data)
    retake = reading.blur_score > BLUR_RETAKE or not reading.format_ok
    doc = Document(id=doc_id, owner_id=cid, kind=kind[:30], file_path=name, ocr_fields=reading.fields,
                   blur_score=reading.blur_score, format_ok=reading.format_ok, confidence=reading.confidence)
    db.add(doc)
    db.flush()
    audit.log(db, "user", user.id, "document.upload", "document", doc.id, after={"citizen_id": cid, "kind": doc.kind, "bytes": len(data)})
    audit.log(db, "ai", "ai:read_document", "ai.read_document", "document", doc.id,
              after={"blur_score": reading.blur_score, "format_ok": reading.format_ok, "confidence": reading.confidence,
                     "model_version": reading.model_version, "fields_read": sorted(reading.fields)})
    db.commit()
    if retake:
        ur, en = "تصویر صاف نہیں ہے۔ براہ کرم روشنی میں کارڈ سیدھا رکھ کر دوبارہ تصویر لیں۔", "The photo is not clear. Please retake it in good light with the card flat."
    else:
        ur, en = "تصویر صاف ہے۔ نام اور شناختی نمبر پڑھ لیے گئے ہیں۔", "The photo is clear. Name and ID number were read."
    return {"document_id": doc.id, "fields": reading.fields, "blur_score": reading.blur_score, "format_ok": reading.format_ok,
            "confidence": reading.confidence, "retake_needed": retake, "explanation_ur": ur, "explanation_en": en,
            "model_version": reading.model_version}
