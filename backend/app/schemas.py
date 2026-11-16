from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Auth ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(ORMModel):
    id: int
    username: str
    real_name: Optional[str] = None
    role: str
    is_active: Optional[bool] = True


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: Optional[str] = None
    role: str = "duty"
    is_active: Optional[bool] = True


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    token: str
    user: UserOut


# ---------- Area ----------
class AreaCreate(BaseModel):
    name: str
    building: Optional[str] = None
    floor: Optional[str] = None


class AreaOut(ORMModel):
    id: int
    name: str
    building: Optional[str] = None
    floor: Optional[str] = None


# ---------- Device ----------
def _strip_not_blank(value):
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("不能为空白")
    return value


class DeviceCreate(BaseModel):
    device_no: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    device_type: str
    area_id: Optional[int] = None
    x: Optional[float] = Field(None, ge=0, le=100)
    y: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[str] = "normal"
    install_date: Optional[str] = None
    remark: Optional[str] = None

    @field_validator("device_no", "name")
    @classmethod
    def _strip_blank(cls, v):
        return _strip_not_blank(v)


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    device_type: Optional[str] = None
    area_id: Optional[int] = None
    x: Optional[float] = Field(None, ge=0, le=100)
    y: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[str] = None
    install_date: Optional[str] = None
    remark: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _strip_blank(cls, v):
        return _strip_not_blank(v)


class DeviceStatusUpdate(BaseModel):
    status: str


class DeviceOut(ORMModel):
    id: int
    device_no: str
    name: str
    device_type: str
    area_id: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None
    status: str
    install_date: Optional[str] = None
    remark: Optional[str] = None
    area: Optional[AreaOut] = None


class DeviceListOut(BaseModel):
    total: int
    items: List[DeviceOut]


# ---------- Plan ----------
class PlanAction(BaseModel):
    action_type: str
    action_name: str


class PlanCreate(BaseModel):
    name: str
    area_id: Optional[int] = None
    fire_type: Optional[str] = "ordinary"
    actions: List[PlanAction] = []
    enabled: Optional[bool] = True


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    area_id: Optional[int] = None
    fire_type: Optional[str] = None
    actions: Optional[List[PlanAction]] = None
    enabled: Optional[bool] = None


class PlanOut(ORMModel):
    id: int
    name: str
    area_id: Optional[int] = None
    fire_type: Optional[str] = None
    actions: Optional[list] = None
    enabled: Optional[bool] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    area: Optional[AreaOut] = None


# ---------- Alarm ----------
class AlarmSimulate(BaseModel):
    device_id: int
    fire_type: str
    scene: Optional[str] = None


class AlarmOut(ORMModel):
    id: int
    device_id: int
    fire_type: Optional[str] = None
    trigger_at: Optional[datetime] = None
    status: str
    confirm_by: Optional[str] = None
    confirm_at: Optional[datetime] = None
    false_reason: Optional[str] = None
    scene: Optional[str] = None
    device: Optional[DeviceOut] = None


class AlarmConfirm(BaseModel):
    result: str
    false_reason: Optional[str] = None
    scene: Optional[str] = None


# ---------- Linkage ----------
class LinkageOut(ORMModel):
    id: int
    plan_id: Optional[int] = None
    alarm_id: Optional[int] = None
    owner_id: Optional[int] = None
    trigger_type: Optional[str] = None
    trigger_at: Optional[datetime] = None
    status: str


class LinkageResultOut(ORMModel):
    id: int
    run_id: int
    action_type: Optional[str] = None
    action_name: Optional[str] = None
    status: str
    execute_at: Optional[datetime] = None
    detail: Optional[str] = None


class LinkageRunDetail(LinkageOut):
    results: List[LinkageResultOut] = []


# ---------- Emergency ----------
class EmergencyCreate(BaseModel):
    alarm_id: Optional[int] = None
    title: str


class EmergencyRecordCreate(BaseModel):
    time: str
    content: str
    person: Optional[str] = None


class EmergencyClose(BaseModel):
    result: str


class RecordOut(ORMModel):
    id: int
    emergency_id: int
    time: Optional[str] = None
    content: Optional[str] = None
    person: Optional[str] = None


class EmergencyOut(ORMModel):
    id: int
    alarm_id: Optional[int] = None
    title: Optional[str] = None
    start_at: Optional[datetime] = None
    status: str
    result: Optional[str] = None
    closed_by: Optional[str] = None
    closed_at: Optional[datetime] = None


class EmergencyDetail(EmergencyOut):
    records: List[RecordOut] = []
    alarm: Optional[AlarmOut] = None


# ---------- Patrol ----------
class PatrolCreate(BaseModel):
    device_id: Optional[int] = None
    area_id: Optional[int] = None
    scheduled_date: Optional[str] = None
    status: Optional[str] = "pending"
    patrol_by: Optional[str] = None
    result: Optional[str] = None
    suggest: Optional[str] = None


class PatrolResult(BaseModel):
    status: str
    result: Optional[str] = None
    suggest: Optional[str] = None


class PatrolOut(ORMModel):
    id: int
    device_id: Optional[int] = None
    area_id: Optional[int] = None
    scheduled_date: Optional[str] = None
    status: str
    patrol_by: Optional[str] = None
    patrol_time: Optional[datetime] = None
    result: Optional[str] = None
    suggest: Optional[str] = None
    overdue: Optional[bool] = False


# ---------- Repair ----------
class RepairCreate(BaseModel):
    device_id: int
    title: str
    description: Optional[str] = None
    creator: Optional[str] = None
    patrol_id: Optional[int] = None


class RepairFinish(BaseModel):
    result: str


class RepairOut(ORMModel):
    id: int
    patrol_id: Optional[int] = None
    device_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    result: Optional[str] = None


# ---------- Drill ----------
class DrillCreate(BaseModel):
    title: str
    drill_type: Optional[str] = None
    area_id: Optional[int] = None
    plan_date: Optional[str] = None
    status: Optional[str] = "planned"
    organizer: Optional[str] = None
    participants: Optional[str] = None
    process: Optional[str] = None
    duration: Optional[int] = None


class DrillUpdate(BaseModel):
    title: Optional[str] = None
    drill_type: Optional[str] = None
    area_id: Optional[int] = None
    plan_date: Optional[str] = None
    status: Optional[str] = None
    organizer: Optional[str] = None
    participants: Optional[str] = None
    process: Optional[str] = None
    duration: Optional[int] = None


class DrillFinish(BaseModel):
    score: Optional[float] = None
    evaluate: Optional[str] = None
    summary: Optional[str] = None


class DrillOut(ORMModel):
    id: int
    title: Optional[str] = None
    drill_type: Optional[str] = None
    area_id: Optional[int] = None
    plan_date: Optional[str] = None
    status: str
    organizer: Optional[str] = None
    participants: Optional[str] = None
    process: Optional[str] = None
    duration: Optional[int] = None
    score: Optional[float] = None
    evaluate: Optional[str] = None
    summary: Optional[str] = None