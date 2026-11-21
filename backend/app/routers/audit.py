"""Read-only view of the append-only audit log. There are deliberately no update/delete routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
from app.auth import require_role
from app.db import get_db
from app.models import AuditLog
from app.services.serialize import iso
from contracts.enums import Role
from contracts.schemas import AuditListResponse

router = APIRouter(tags=["audit"], route_class=CompactRoute)


@router.get("/audit", response_model=AuditListResponse)
def list_audit(actor_id: Optional[str] = None, actor_type: Optional[str] = None, action: Optional[str] = None,
               entity: Optional[str] = None, entity_id: Optional[str] = None, request_id: Optional[str] = None,
               limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
               user=Depends(require_role(Role.auditor, Role.admin)), db: Session = Depends(get_db)):
    conds = []
    for col, val in ((AuditLog.actor_id, actor_id), (AuditLog.actor_type, actor_type), (AuditLog.action, action),
                     (AuditLog.entity, entity), (AuditLog.entity_id, entity_id), (AuditLog.request_id, request_id)):
        if val:
            conds.append(col == val)
    total = db.execute(select(func.count()).select_from(AuditLog).where(*conds)).scalar_one()
    rows = db.execute(select(AuditLog).where(*conds).order_by(AuditLog.id.desc()).limit(limit).offset(offset)).scalars().all()
    items = [{"id": str(r.id), "timestamp": iso(r.created_at), "actor": r.actor_id or r.actor_type,
              "actor_type": r.actor_type, "action": r.action, "target": "%s:%s" % (r.entity, r.entity_id or ""),
              "entity": r.entity, "entity_id": r.entity_id, "request_id": r.request_id,
              "before": r.before, "after": r.after} for r in rows]
    return {"items": items, "total": total}
