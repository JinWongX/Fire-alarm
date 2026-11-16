from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
    text,
)
from sqlalchemy.orm import relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    real_name = Column(String)
    role = Column(String, default="duty")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)


class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    building = Column(String)
    floor = Column(String)

    devices = relationship("Device", back_populates="area")
    plans = relationship("Plan", back_populates="area")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_no = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"))
    x = Column(Float)
    y = Column(Float)
    status = Column(String, default="normal")
    install_date = Column(String)
    remark = Column(Text)

    area = relationship("Area", back_populates="devices")
    alarms = relationship("Alarm", back_populates="device")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    area_id = Column(Integer, ForeignKey("areas.id"))
    fire_type = Column(String)
    actions = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    area = relationship("Area", back_populates="plans")
    runs = relationship("LinkageRun", back_populates="plan")


Index("ix_plans_area_fire_type", Plan.area_id, Plan.fire_type, unique=True, sqlite_where=text("area_id IS NOT NULL"))


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    fire_type = Column(String)
    trigger_at = Column(DateTime, default=utcnow)
    status = Column(String, default="pending")
    confirm_by = Column(String)
    confirm_at = Column(DateTime)
    false_reason = Column(String)
    scene = Column(Text)

    device = relationship("Device", back_populates="alarms")
    emergencies = relationship("Emergency", back_populates="alarm")


class LinkageRun(Base):
    __tablename__ = "linkage_runs"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    alarm_id = Column(Integer, ForeignKey("alarms.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    trigger_type = Column(String, default="manual")
    trigger_at = Column(DateTime, default=utcnow)
    status = Column(String, default="success")

    plan = relationship("Plan", back_populates="runs")
    alarm = relationship("Alarm")
    results = relationship("LinkageResult", back_populates="run", cascade="all, delete-orphan")


class LinkageResult(Base):
    __tablename__ = "linkage_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("linkage_runs.id"))
    action_type = Column(String)
    action_name = Column(String)
    status = Column(String, default="success")
    execute_at = Column(DateTime, default=utcnow)
    detail = Column(Text)

    run = relationship("LinkageRun", back_populates="results")


class Emergency(Base):
    __tablename__ = "emergencies"

    id = Column(Integer, primary_key=True, index=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id"), nullable=True)
    title = Column(String)
    start_at = Column(DateTime, default=utcnow)
    status = Column(String, default="active")
    result = Column(Text)
    closed_by = Column(String)
    closed_at = Column(DateTime)

    alarm = relationship("Alarm", back_populates="emergencies")
    records = relationship("EmergencyRecord", back_populates="emergency", cascade="all, delete-orphan")


Index("ix_emergencies_alarm_id", Emergency.alarm_id, unique=True)


class EmergencyRecord(Base):
    __tablename__ = "emergency_records"

    id = Column(Integer, primary_key=True, index=True)
    emergency_id = Column(Integer, ForeignKey("emergencies.id"))
    time = Column(String)
    content = Column(Text)
    person = Column(String)

    emergency = relationship("Emergency", back_populates="records")


class Patrol(Base):
    __tablename__ = "patrols"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    area_id = Column(Integer, ForeignKey("areas.id"))
    scheduled_date = Column(String)
    status = Column(String, default="pending")
    patrol_by = Column(String)
    patrol_time = Column(DateTime)
    result = Column(Text)
    suggest = Column(Text)


class Repair(Base):
    __tablename__ = "repairs"

    id = Column(Integer, primary_key=True, index=True)
    patrol_id = Column(Integer, ForeignKey("patrols.id"), nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    title = Column(String)
    description = Column(Text)
    creator = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=utcnow)
    closed_at = Column(DateTime)
    result = Column(Text)


Index("ix_repairs_patrol_id", Repair.patrol_id, unique=True)


class Drill(Base):
    __tablename__ = "drills"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    drill_type = Column(String)
    area_id = Column(Integer, ForeignKey("areas.id"))
    plan_date = Column(String)
    status = Column(String, default="planned")
    organizer = Column(String)
    participants = Column(Text)
    process = Column(Text)
    duration = Column(Integer)
    score = Column(Float)
    evaluate = Column(Text)
    summary = Column(Text)