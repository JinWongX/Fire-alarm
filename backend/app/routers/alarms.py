from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..link_engine import execute_linkage, get_matching_plan
from ..models import Alarm, Device, Emergency, LinkageRun, User, utcnow
from ..schemas import (
    AlarmConfirm,
    AlarmOut,
    AlarmSimulate,
)

router = APIRouter(prefix="/api/alarms", tags=["alarms"])

FIRE_TYPES = ["electrical", "ordinary", "oil", "other"]


@router.post("/simulate")
def simulate_alarm(
    body: AlarmSimulate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    dev = db.query(Device).filter(Device.id == body.device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    if body.fire_type not in FIRE_TYPES:
        raise HTTPException(status_code=400, detail="无效的火灾类型")

    dev.status = "alarm"
    alarm = Alarm(
        device_id=dev.id,
        fire_type=body.fire_type,
        scene=body.scene,
        status="pending",
        trigger_at=utcnow(),
    )
    db.add(alarm)
    db.flush()

    plan = get_matching_plan(db, dev.area_id, body.fire_type)
    run = execute_linkage(
        db, plan, alarm_id=alarm.id, owner_id=current_user.id, trigger_type="auto"
    )
    db.commit()
    db.refresh(alarm)

    return {
        "alarm": AlarmOut.model_validate(alarm),
        "linkage_run": (
            {"id": run.id, "plan_id": run.plan_id, "status": run.status, "trigger_type": run.trigger_type}
            if run
            else None
        ),
    }


@router.get("")
def list_alarms(
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    query = db.query(Alarm)
    if status:
        query = query.filter(Alarm.status == status)
    total = query.count()
    items = (
        query.options(joinedload(Alarm.device))
        .order_by(Alarm.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "items": [AlarmOut.model_validate(a) for a in items]}


@router.post("/{alarm_id}/confirm")
def confirm_alarm(
    alarm_id: int,
    body: AlarmConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="报警不存在")

    if body.result not in ("true", "false"):
        raise HTTPException(status_code=400, detail="result 必须为 true 或 false")

    if alarm.status != "pending":
        if alarm.status == "confirmed_real" and body.result == "true":
            existing = (
                db.query(Emergency).filter(Emergency.alarm_id == alarm.id).first()
            )
            return {
                "alarm": AlarmOut.model_validate(alarm),
                "emergency": (
                    {"id": existing.id, "title": existing.title, "status": existing.status}
                    if existing
                    else None
                ),
            }
        if alarm.status == "confirmed_false" and body.result == "false":
            return {"alarm": AlarmOut.model_validate(alarm), "emergency": None}
        raise HTTPException(status_code=409, detail="已确认的报警不允许改判")

    alarm.confirm_by = current_user.username
    alarm.confirm_at = utcnow()

    if body.result == "false":
        if not body.false_reason:
            raise HTTPException(status_code=400, detail="确认为误报时必须填写误报原因")
        alarm.status = "confirmed_false"
        alarm.false_reason = body.false_reason
        dev = db.query(Device).filter(Device.id == alarm.device_id).first()
        if dev:
            dev.status = "normal"
        db.commit()
        return {"alarm": AlarmOut.model_validate(alarm), "emergency": None}

    alarm.status = "confirmed_real"
    if body.scene:
        alarm.scene = body.scene
    device = db.query(Device).filter(Device.id == alarm.device_id).first()
    area_name = device.area.name if device and device.area else "未知区域"
    title = f"{area_name}消防处置（{alarm.fire_type}）"
    emergency = (
        db.query(Emergency).filter(Emergency.alarm_id == alarm.id).first()
    )
    if emergency is None:
        emergency = Emergency(
            alarm_id=alarm.id,
            title=title,
            status="active",
            start_at=utcnow(),
        )
        db.add(emergency)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        emergency = (
            db.query(Emergency).filter(Emergency.alarm_id == alarm.id).first()
        )
        alarm = db.query(Alarm).filter(Alarm.id == alarm.id).first()
        alarm.status = "confirmed_real"
        alarm.confirm_by = current_user.username
        alarm.confirm_at = utcnow()
        if body.scene:
            alarm.scene = body.scene
        db.commit()
    db.refresh(alarm)
    db.refresh(emergency)
    return {"alarm": AlarmOut.model_validate(alarm), "emergency": {"id": emergency.id, "title": emergency.title, "status": emergency.status}}