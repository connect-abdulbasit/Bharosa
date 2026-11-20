from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import require_role
from app.fixtures import fixture
from app.services import audit
from contracts.enums import Role
from contracts.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(file: Optional[UploadFile] = File(None), user=Depends(require_role(Role.citizen, Role.helper))):
    # TODO(Basit): read bytes, bharosa_ai.read_document, blur check -> ask retake. Do not store raw images long-term.
    audit.log("ai:read_document", "ai.read_document", None, {"filename": getattr(file, "filename", None)}, target=user["user_id"], actor_type="ai")
    return fixture("document_upload")
