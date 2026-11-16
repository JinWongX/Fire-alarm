from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..models import Device, Patrol, Repair, User, utcnow
from ..schemas import (
    PatrolCreate,
    PatrolOut,
    PatrolResult,
)

router = APIRouter(prefix="/api/patrols", tags=["patrols"])

PATROL_ROLES = ("maintenance", "supervisor")


def _is_overdue(patrol) -> bool:
    if patrol.status != "pending" or not patrol.scheduled_date:
        return False
    try:
        return patrol.scheduled_date < date.today().strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return False


def _to_out(patrol) -> PatrolOut:
    out = PatrolOut.model_validate(patrol)
    out.overdue = _is_overdue(patrol)
    return out


@router.get("", response_model=list[PatrolOut])
def list_patrols(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return [_to_out(p) for p in db.query(Patrol).order_by(Patrol.id.desc()).all()]


@router.get("/summary")
def patrol_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    total = db.query(Patrol).count()
    done = db.query(Patrol).filter(Patrol.status.in_(["normal", "abnormal"])).count()
    abnormal = db.query(Patrol).filter(Patrol.status == "abnormal").count()
    overdue = sum(1 for p in db.query(Patrol).all() if _is_overdue(p))
    rate = round(done / total * 100, 1) if total else 0.0
    return {"total": total, "done": done, "abnormal": abnormal, "overdue": overdue, "done_rate": rate}


@router.post("", response_model=PatrolOut, status_code=201)
def create_patrol(
    body: PatrolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(*PATROL_ROLES)),
):
    patrol = Patrol(**body.model_dump(exclude_unset=True))
    patrol.status = body.status or "pending"
    db.add(patrol)
    db.commit()
    db.refresh(patrol)
    return PatrolOut.model_validate(patrol)


@router.post("/{patrol_id}/result", response_model=PatrolOut)
def submit_result(
    patrol_id: int,
    body: PatrolResult,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(*PATROL_ROLES)),
):
    patrol = db.query(Patrol).filter(Patrol.id == patrol_id).first()
    if not patrol:
        raise HTTPException(status_code=404, detail="巡检任务不存在")
    if body.status not in ("normal", "abnormal"):
        raise HTTPException(status_code=400, detail="巡检结果必须为 normal 或 abnormal")

    if body.status == "abnormal" and not (body.result or body.suggest):
        raise HTTPException(status_code=400, detail="异常巡检必须填写异常说明（result 或 suggest）")

    if patrol.status != "pending":
        if patrol.status == body.status:
            return PatrolOut.model_validate(patrol)
        raise HTTPException(status_code=409, detail="巡检任务已提交结果，不允许重复提交")

    patrol.status = body.status
    patrol.result = body.result
    patrol.suggest = body.suggest
    patrol.patrol_by = current_user.username or patrol.patrol_by
    patrol.patrol_time = utcnow()

    if body.status == "abnormal":
        dev = db.query(Device).filter(Device.id == patrol.device_id).first() if patrol.device_id else None
        active = None
        if patrol.device_id:
            active = (
                db.query(Repair)
                .filter(
                    Repair.device_id == patrol.device_id,
                    Repair.status.in_(["pending", "in_progress"]),
                )
                .first()
            )
        if active is None:
            repair_title = f"{dev.name if dev else '设备'}异常维修" if dev else "设备异常维修"
            repair = Repair(
                patrol_id=patrol.id,
                device_id=patrol.device_id,
                title=repair_title,
                description=body.result or body.suggest or "巡检发现异常",
                creator=current_user.username,
                status="pending",
            )
            db.add(repair)
        elif not active.patrol_id:
            active.patrol_id = patrol.id
        if dev:
            dev.status = "fault"

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        patrol = db.query(Patrol).filter(Patrol.id == patrol.id).first()
        patrol.status = body.status
        patrol.result = body.result
        patrol.suggest = body.suggest
        patrol.patrol_by = current_user.username or patrol.patrol_by
        patrol.patrol_time = utcnow()
        db.commit()
    db.refresh(patrol)
    return PatrolOut.model_validate(patrol)