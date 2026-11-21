"""ID photo upload and retrieval. Stored in Postgres after a server-side resize; OCR + blur check run on the stored JPEG."""
import uuid
from typing import Optional

import bharosa_ai as ai
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import ANY_ROLE, require_role
from app.config import settings
from app.db import get_db
from app.models import Document, User
from app.routing import CompactRoute
from app.services import audit
from app.services import documents as doc_store
from app.services.access import can_access_citizen, resolve_citizen
from app.services.images import ImageRejected, ImageTooLarge, process_image
from contracts.enums import Role
from contracts.schemas import DocumentResponse

router = APIRouter(tags=["documents"], route_class=CompactRoute)
MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF")
BLUR_RETAKE = 0.5


def sniff_ok(data: bytes) -> bool:
    return any(data.startswith(m) for m in MAGIC) and (not data.startswith(b"RIFF") or data[8:12] == b"WEBP")


@router.post("/documents", response_model=DocumentResponse, summary="Upload an ID photo (resized + stored in the database)")
async def upload_document(file: UploadFile = File(...), kind: str = Form("id_card"), citizen_id: Optional[str] = Form(None),
                          user: User = Depends(require_role(Role.citizen, Role.helper)), db: Session = Depends(get_db)):
    """PNG, JPEG or WebP up to 10 MB. The server re-encodes it as a JPEG of at most 1280 px (quality 80, EXIF removed, under 2 MB),
    stores it in Postgres and runs OCR + a blur check; `retake_needed` tells the user to retake an unclear photo.
    Helpers must name the citizen and pass the family link check."""
    cid = resolve_citizen(db, user, citizen_id)
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (max %d MB)" % (settings.MAX_UPLOAD_BYTES // (1024 * 1024)))
    if not sniff_ok(data):
        raise HTTPException(status_code=415, detail="Please upload a PNG, JPEG or WebP photo")
    try:
        jpeg, width, height = process_image(data)
    except ImageRejected:
        raise HTTPException(status_code=415, detail="That file is not a readable photo")
    except ImageTooLarge:
        raise HTTPException(status_code=413, detail="The photo is too large even after shrinking it")

    doc = Document(id=str(uuid.uuid4()), owner_id=cid, kind=kind[:30])
    db.add(doc)
    db.flush()
    doc_store.store(db, doc, jpeg, width, height)
    reading = ai.read_document(jpeg)
    retake = reading.blur_score > BLUR_RETAKE or not reading.format_ok
    doc.ocr_fields, doc.blur_score, doc.format_ok, doc.confidence = reading.fields, reading.blur_score, reading.format_ok, reading.confidence
    audit.log(db, "user", user.id, "document.upload", "document", doc.id,
              after={"citizen_id": cid, "kind": doc.kind, "bytes_in": len(data), "bytes_stored": len(jpeg), "size": "%dx%d" % (width, height)})
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
            "model_version": reading.model_version, "image_url": "/documents/%s/image" % doc.id}


@router.get("/documents/{document_id}/image", summary="The stored ID photo (same access rules as the case)",
            responses={200: {"content": {"image/jpeg": {}}, "description": "The JPEG"}})
def document_image(document_id: str, user: User = Depends(ANY_ROLE), db: Session = Depends(get_db)):
    """Allowed: the citizen it belongs to, a helper linked to that citizen, officers, admins and auditors (read-only).
    Anyone else gets 404 (not 403) so the existence of a photo is not revealed. Every view is audited."""
    doc = db.get(Document, document_id)
    if doc is None or doc.owner_id is None or not can_access_citizen(db, user, doc.owner_id):
        raise HTTPException(status_code=404, detail="Document not found")
    content = doc_store.load(db, doc)
    if content is None:
        raise HTTPException(status_code=404, detail="Document not found")
    audit.log(db, "user", user.id, "document.view", "document", doc.id, after={"citizen_id": doc.owner_id, "bytes": len(content)})
    db.commit()
    return Response(content=content, media_type="image/jpeg",
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Content-Disposition": "inline"})
