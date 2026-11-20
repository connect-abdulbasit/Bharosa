from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_role
from app.db import get_db
from app.fixtures import fixture
from app.models import User
from app.services import audit
from contracts.enums import Role
from contracts.schemas import DocumentResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentResponse)
async def upload_document(file: Optional[UploadFile] = File(None), user: User = Depends(require_role(Role.citizen, Role.helper)),
                          db: Session = Depends(get_db)):
    # TODO(Basit): read bytes, bharosa_ai.read_document, blur check -> ask retake, save a documents row. Do not keep raw images.
    audit.log(db, "ai", "read_document", "ai.read_document", "document", None,
              after={"filename": getattr(file, "filename", None), "requested_by": user.id})
    db.commit()
    return fixture("document_upload")
