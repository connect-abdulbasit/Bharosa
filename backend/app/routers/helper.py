from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.routing import CompactRoute
from app.auth import require_role
from app.db import get_db
from app.models import Case, Family, User
from app.services import consent as consent_service
from contracts.enums import Role
from contracts.schemas import HelperFamiliesResponse

router = APIRouter(tags=["helper"], route_class=CompactRoute)


@router.get("/helper/families", response_model=HelperFamiliesResponse)
def families(user: User = Depends(require_role(Role.helper)), db: Session = Depends(get_db)):
    """Only the citizens linked to THIS helper."""
    items = []
    for fam in db.execute(select(Family).where(Family.helper_id == user.id).order_by(Family.id)).scalars():
        citizen = db.get(User, fam.citizen_id)
        cases = db.execute(select(Case).where(Case.citizen_id == fam.citizen_id).order_by(Case.updated_at.desc())).scalars().all()
        ident = consent_service.get_consent(db, fam.citizen_id, "identity")
        last = cases[0] if cases else None
        items.append({"family_id": fam.id, "citizen_id": fam.citizen_id, "head_name": citizen.name, "case_count": len(cases),
                      "open_cases": sum(1 for c in cases if c.status != "closed"),
                      "last_action": ("Case %s" % last.status.replace("_", " ")) if last else "No cases yet",
                      "latest_case_status": last.status if last else None,
                      "consent_on_file": bool(ident and ident.status == "granted")})
    return {"items": items}
