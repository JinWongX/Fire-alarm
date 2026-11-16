from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..models import Alarm, Emergency, EmergencyRecord, User, utcnow
from ..schemas import (
    EmergencyCreate,
    EmergencyClose,
    EmergencyDetail,
    EmergencyOut,
    EmergencyRecordCreate,
    RecordOut,
)

router = APIRouter(prefix="/api/emergencies", tags=["emergencies"])


@router.get("", response_model=list[EmergencyOut])
def list_emergencies(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(Emergency).order_by(Emergency.id.desc()).all()


@router.get("/{emergency_id}", response_model=EmergencyDetail)
def get_emergency(
    emergency_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    em = db.query(Emergency).filter(Emergency.id == emergency_id).first()
    if not em:
        raise HTTPException(status_code=404, detail="处置单不存在")
    return EmergencyDetail.model_validate(em)


@router.post("", response_model=EmergencyOut, status_code=201)
def create_emergency(
    body: EmergencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    em = Emergency(
        alarm_id=body.alarm_id,
        title=body.title,
        status="active",
        start_at=utcnow(),
    )
    db.add(em)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该报警已存在处置单")
    db.refresh(em)
    return EmergencyOut.model_validate(em)


@router.post("/{emergency_id}/records", response_model=RecordOut)
def add_record(
    emergency_id: int,
    body: EmergencyRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    em = db.query(Emergency).filter(Emergency.id == emergency_id).first()
    if not em:
        raise HTTPException(status_code=404, detail="处置单不存在")
    record = EmergencyRecord(
        emergency_id=em.id,
        time=body.time,
        content=body.content,
        person=body.person or current_user.username,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return RecordOut.model_validate(record)


@router.post("/{emergency_id}/close", response_model=EmergencyOut)
def close_emergency(
    emergency_id: int,
    body: EmergencyClose,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    em = db.query(Emergency).filter(Emergency.id == emergency_id).first()
    if not em:
        raise HTTPException(status_code=404, detail="处置单不存在")
    em.status = "closed"
    em.result = body.result
    em.closed_by = current_user.username
    em.closed_at = utcnow()
    db.commit()
    db.refresh(em)
    return EmergencyOut.model_validate(em)