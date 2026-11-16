from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Area, User
from ..schemas import AreaOut

router = APIRouter(prefix="/api/areas", tags=["areas"])


@router.get("", response_model=list[AreaOut])
def list_areas(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Area).order_by(Area.id).all()