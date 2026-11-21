"""Where ID photos live: Postgres (documents_blob) is the source of truth; a local disk copy is an optional cache."""
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentBlob


def cache_path(doc: Document):
    return settings.UPLOAD_DIR / doc.file_path if doc.file_path else None


def store(db: Session, doc: Document, jpeg: bytes, width: int, height: int) -> None:
    db.add(DocumentBlob(document_id=doc.id, content=jpeg, content_type="image/jpeg", size_bytes=len(jpeg), width=width, height=height))
    if settings.DOCUMENT_DISK_CACHE:
        try:
            settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            doc.file_path = doc.id + ".jpg"
            (settings.UPLOAD_DIR / doc.file_path).write_bytes(jpeg)
        except OSError:
            doc.file_path = None  # a cache failure must never fail the upload


def load(db: Session, doc: Document) -> Optional[bytes]:
    """The image bytes: the disk cache if it is there, otherwise the database."""
    path = cache_path(doc)
    if path is not None:
        try:
            return path.read_bytes()
        except OSError:
            pass
    blob = db.get(DocumentBlob, doc.id)
    return blob.content if blob is not None else None
