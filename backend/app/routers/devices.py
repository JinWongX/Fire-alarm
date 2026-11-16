from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..models import Alarm, Area, Device, Patrol, Repair, User
from ..schemas import (
    DeviceCreate,
    DeviceOut,
    DeviceUpdate,
    DeviceStatusUpdate,
    DeviceListOut,
)

router = APIRouter(prefix="/api/devices", tags=["devices"])

DEVICE_TYPES = [
    "smoke",
    "temp",
    "manual",
    "hydrant",
    "sprinkler",
    "smoke_exhaust",
    "fire_door",
    "emergency_light",
]
DEVICE_STATUS = ["normal", "alarm", "fault", "masked"]


def _validate_area_ref(db: Session, area_id):
    if area_id is not None and not db.query(Area).filter(Area.id == area_id).first():
        raise HTTPException(status_code=400, detail="所属区域不存在")


@router.get("", response_model=DeviceListOut)
def list_devices(
    device_type: str | None = None,
    status: str | None = None,
    area_id: int | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    query = db.query(Device)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if status:
        query = query.filter(Device.status == status)
    if area_id:
        query = query.filter(Device.area_id == area_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.outerjoin(Area).filter(
            or_(
                Device.name.ilike(like),
                Device.device_no.ilike(like),
                Area.name.ilike(like),
            )
        )
    total = query.count()
    items = query.order_by(Device.id).offset((page - 1) * page_size).limit(page_size).all()
    return DeviceListOut(total=total, items=[DeviceOut.model_validate(d) for d in items])


@router.post("", response_model=DeviceOut, status_code=201)
def create_device(
    body: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    if body.device_type not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail="无效的设备类型")
    if db.query(Device).filter(Device.device_no == body.device_no).first():
        raise HTTPException(status_code=400, detail="设备编号已存在")
    _validate_area_ref(db, body.area_id)
    dev = Device(**body.model_dump(exclude={"status"}))
    dev.status = body.status or "normal"
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return DeviceOut.model_validate(dev)


@router.get("/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    return DeviceOut.model_validate(dev)


@router.put("/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: int,
    body: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    data = body.model_dump(exclude_unset=True)
    if "area_id" in data:
        _validate_area_ref(db, data["area_id"])
    if "device_type" in data and data["device_type"] is not None and data["device_type"] not in DEVICE_TYPES:
        raise HTTPException(status_code=400, detail="无效的设备类型")
    if "status" in data and data["status"] is not None and data["status"] not in DEVICE_STATUS:
        raise HTTPException(status_code=400, detail="无效的状态")
    for key, value in data.items():
        if value is not None:
            setattr(dev, key, value)
    db.commit()
    db.refresh(dev)
    return DeviceOut.model_validate(dev)


@router.put("/{device_id}/status", response_model=DeviceOut)
def update_device_status(
    device_id: int,
    body: DeviceStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    if body.status not in DEVICE_STATUS:
        raise HTTPException(status_code=400, detail="无效的状态")
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    dev.status = body.status
    db.commit()
    db.refresh(dev)
    return DeviceOut.model_validate(dev)


@router.delete("/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="设备不存在")
    if db.query(Alarm).filter(Alarm.device_id == device_id).first():
        raise HTTPException(status_code=409, detail="设备存在关联报警，无法删除")
    if (
        db.query(Patrol).filter(Patrol.device_id == device_id).first()
        or db.query(Repair).filter(Repair.device_id == device_id).first()
    ):
        raise HTTPException(status_code=409, detail="设备存在关联巡检或维修记录")
    db.delete(dev)
    db.commit()
    return {"ok": True}