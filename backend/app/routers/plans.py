from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user, RoleDependency
from ..database import get_db
from ..link_engine import execute_linkage
from ..models import LinkageRun, Plan, User
from ..schemas import (
    PlanCreate,
    PlanOut,
    PlanUpdate,
)

router = APIRouter(prefix="/api/plans", tags=["plans"])

ACTION_TYPES = [
    "smoke_exhaust",
    "fire_door",
    "emergency_light",
    "broadcast",
]

FIRE_TYPES = ["electrical", "ordinary", "oil", "other"]


def _resolve_fire_type(body):
    fire_type = getattr(body, "fire_type", None) or "ordinary"
    if fire_type not in FIRE_TYPES:
        raise HTTPException(status_code=400, detail="无效的火灾类型")
    return fire_type


def _validate_actions(actions):
    if not actions:
        raise HTTPException(status_code=400, detail="预案至少需要一条联动动作")
    for a in actions:
        action_type = a.get("action_type") if isinstance(a, dict) else a.action_type
        action_name = a.get("action_name") if isinstance(a, dict) else a.action_name
        if not action_type or not action_name:
            raise HTTPException(status_code=400, detail="联动动作缺少 action_type 或 action_name")
        if action_type not in ACTION_TYPES:
            raise HTTPException(status_code=400, detail="无效的联动动作类型")
    return [a.model_dump() if not isinstance(a, dict) else a for a in actions]


def _check_unique(db, area_id, fire_type, exclude_id=None):
    if fire_type is None:
        return
    query = db.query(Plan).filter(Plan.area_id == area_id, Plan.fire_type == fire_type)
    if exclude_id is not None:
        query = query.filter(Plan.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="该区域下已存在相同火灾类型的预案")


@router.get("/actions")
def plan_actions(current_user: User = Depends(get_current_user)):
    return ACTION_TYPES


@router.get("", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Plan).order_by(Plan.id).all()


@router.post("", response_model=PlanOut, status_code=201)
def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    _resolve_fire_type(body)
    actions = _validate_actions(body.actions)
    _check_unique(db, body.area_id, body.fire_type or "ordinary")
    plan = Plan(
        name=body.name,
        area_id=body.area_id,
        fire_type=body.fire_type or "ordinary",
        actions=actions,
        enabled=body.enabled if body.enabled is not None else True,
        created_by=current_user.id,
    )
    db.add(plan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该区域下已存在相同火灾类型的预案")
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.put("/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    body: PlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="预案不存在")
    data = body.model_dump(exclude_unset=True)
    if "fire_type" in data and data["fire_type"] is not None:
        _resolve_fire_type(body)
    if "actions" in data and data["actions"] is not None:
        data["actions"] = _validate_actions(data["actions"])
    if "area_id" in data or "fire_type" in data:
        new_area = data.get("area_id", plan.area_id)
        new_fire = data.get("fire_type", plan.fire_type) or "ordinary"
        _check_unique(db, new_area, new_fire, exclude_id=plan.id)
    for key, value in data.items():
        if value is not None:
            setattr(plan, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该区域下已存在相同火灾类型的预案")
    db.refresh(plan)
    return PlanOut.model_validate(plan)


@router.delete("/{plan_id}")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("supervisor")),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="预案不存在")
    if db.query(LinkageRun).filter(LinkageRun.plan_id == plan_id).first():
        raise HTTPException(status_code=409, detail="预案存在联动执行记录")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/{plan_id}/execute")
def execute_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency("duty", "supervisor")),
):
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="预案不存在")
    run = execute_linkage(
        db, plan, alarm_id=None, owner_id=current_user.id, trigger_type="manual"
    )
    db.commit()
    return {
        "run": {"id": run.id, "plan_id": run.plan_id, "status": run.status, "trigger_type": run.trigger_type, "trigger_at": run.trigger_at},
    }