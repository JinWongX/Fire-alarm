from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..models import Drill, User
from ..schemas import DrillCreate, DrillFinish, DrillOut, DrillUpdate

router = APIRouter(prefix="/api/drills", tags=["drills"])


@router.get("", response_model=list[DrillOut])
def list_drills(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Drill).order_by(Drill.id.desc()).all()


@router.post("", response_model=DrillOut, status_code=201)
def create_drill(
    body: DrillCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    drill = Drill(**body.model_dump(exclude_unset=True))
    drill.status = body.status or "planned"
    db.add(drill)
    db.commit()
    db.refresh(drill)
    return DrillOut.model_validate(drill)


@router.put("/{drill_id}", response_model=DrillOut)
def update_drill(
    drill_id: int,
    body: DrillUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    drill = db.query(Drill).filter(Drill.id == drill_id).first()
    if not drill:
        raise HTTPException(status_code=404, detail="演练不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(drill, key, value)
    db.commit()
    db.refresh(drill)
    return DrillOut.model_validate(drill)


@router.delete("/{drill_id}")
def delete_drill(
    drill_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    drill = db.query(Drill).filter(Drill.id == drill_id).first()
    if not drill:
        raise HTTPException(status_code=404, detail="演练不存在")
    db.delete(drill)
    db.commit()
    return {"ok": True}


@router.post("/{drill_id}/finish", response_model=DrillOut)
def finish_drill(
    drill_id: int,
    body: DrillFinish,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    drill = db.query(Drill).filter(Drill.id == drill_id).first()
    if not drill:
        raise HTTPException(status_code=404, detail="演练不存在")
    if body.score is not None and not (0 <= body.score <= 100):
        raise HTTPException(status_code=400, detail="评分必须介于 0 到 100 之间")
    drill.status = "done"
    if body.score is not None:
        drill.score = body.score
    if body.evaluate is not None:
        drill.evaluate = body.evaluate
    if body.summary is not None:
        drill.summary = body.summary
    db.commit()
    db.refresh(drill)
    return DrillOut.model_validate(drill)