from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..models import Device, Repair, User, utcnow
from ..schemas import RepairCreate, RepairFinish, RepairOut

router = APIRouter(prefix="/api/repairs", tags=["repairs"])

REPAIR_ROLES = ("maintenance", "supervisor")


@router.get("", response_model=list[RepairOut])
def list_repairs(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(Repair).order_by(Repair.id.desc()).all()


@router.post("", response_model=RepairOut, status_code=201)
def create_repair(
    body: RepairCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(*REPAIR_ROLES)),
):
    if not db.query(Device).filter(Device.id == body.device_id).first():
        raise HTTPException(status_code=404, detail="设备不存在")
    active = (
        db.query(Repair)
        .filter(
            Repair.device_id == body.device_id,
            Repair.status.in_(["pending", "in_progress"]),
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=409, detail="该设备已有进行中的维修单，请勿重复创建")
    repair = Repair(
        patrol_id=body.patrol_id,
        device_id=body.device_id,
        title=body.title,
        description=body.description,
        creator=body.creator or current_user.username,
        status="pending",
    )
    db.add(repair)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该巡检已生成维修单，请勿重复创建")
    db.refresh(repair)
    return RepairOut.model_validate(repair)


@router.post("/{repair_id}/start", response_model=RepairOut)
def start_repair(
    repair_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(*REPAIR_ROLES)),
):
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="维修单不存在")
    affected = (
        db.query(Repair)
        .filter(Repair.id == repair_id, Repair.status == "pending")
        .update({"status": "in_progress"}, synchronize_session=False)
    )
    if affected == 0:
        raise HTTPException(status_code=409, detail="当前维修单状态不允许启动")
    db.commit()
    db.refresh(repair)
    return RepairOut.model_validate(repair)


@router.post("/{repair_id}/finish", response_model=RepairOut)
def finish_repair(
    repair_id: int,
    body: RepairFinish,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(*REPAIR_ROLES)),
):
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="维修单不存在")
    affected = (
        db.query(Repair)
        .filter(Repair.id == repair_id, Repair.status == "in_progress")
        .update(
            {"status": "done", "result": body.result, "closed_at": utcnow()},
            synchronize_session=False,
        )
    )
    if affected == 0:
        raise HTTPException(status_code=409, detail="当前维修单状态不允许完成")
    if repair.device_id:
        dev = db.query(Device).filter(Device.id == repair.device_id).first()
        if dev:
            dev.status = "normal"
    db.commit()
    db.refresh(repair)
    return RepairOut.model_validate(repair)