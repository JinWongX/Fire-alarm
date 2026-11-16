from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..database import get_db
from ..models import LinkageRun, LinkageResult, User
from ..schemas import LinkageOut, LinkageResultOut

router = APIRouter(prefix="/api/linkage", tags=["linkage"])


@router.get("/runs")
def list_runs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    query = db.query(LinkageRun)
    total = query.count()
    runs = (
        query.options(joinedload(LinkageRun.plan), joinedload(LinkageRun.alarm))
        .order_by(LinkageRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for run in runs:
        items.append(
            {
                "id": run.id,
                "plan_id": run.plan_id,
                "alarm_id": run.alarm_id,
                "owner_id": run.owner_id,
                "trigger_type": run.trigger_type,
                "trigger_at": run.trigger_at,
                "status": run.status,
                "plan_name": run.plan.name if run.plan else None,
                "alarm": {"id": run.alarm.id, "fire_type": run.alarm.fire_type, "status": run.alarm.status} if run.alarm else None,
            }
        )
    return {"total": total, "items": items}


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = db.query(LinkageRun).filter(LinkageRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="联动记录不存在")
    results = (
        db.query(LinkageResult).filter(LinkageResult.run_id == run.id).order_by(LinkageResult.id).all()
    )
    return {
        "id": run.id,
        "plan_id": run.plan_id,
        "alarm_id": run.alarm_id,
        "owner_id": run.owner_id,
        "trigger_type": run.trigger_type,
        "trigger_at": run.trigger_at,
        "status": run.status,
        "plan_name": run.plan.name if run.plan else None,
        "results": [LinkageResultOut.model_validate(r) for r in results],
    }