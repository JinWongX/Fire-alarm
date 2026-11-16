import csv
import io
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from ..auth import RoleDependency
from ..database import get_db
from ..models import (
    Alarm,
    Device,
    Drill,
    Emergency,
    LinkageResult,
    Patrol,
    Plan,
    User,
    utcnow,
)

router = APIRouter(prefix="/api/stats", tags=["stats"])

STATS_ROLE = "supervisor"


def _parse_date(value: str | None, name: str):
    if value in (None, ""):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name} 格式必须为 YYYY-MM-DD")


def _sanitize_cell(value):
    """CWE-1236 防护：以 = + - @ 开头的单元格前置单引号，防公式注入。"""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _sanitize_rows(rows):
    return [[_sanitize_cell(c) for c in row] for row in rows]


@router.get("/alarms")
def list_alarm_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(STATS_ROLE)),
):
    alarms = (
        db.query(Alarm)
        .options(joinedload(Alarm.device))
        .order_by(Alarm.id.desc())
        .limit(100)
        .all()
    )
    items = [
        {
            "id": a.id,
            "device_no": a.device.device_no if a.device else None,
            "device_name": a.device.name if a.device else None,
            "fire_type": a.fire_type,
            "trigger_at": a.trigger_at,
            "status": a.status,
            "false_reason": a.false_reason,
            "scene": a.scene,
        }
        for a in alarms
    ]
    return {"total": len(items), "items": items}


@router.get("/dashboard")
def dashboard(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(STATS_ROLE)),
):
    from_dt = _parse_date(from_, "from")
    to_dt = _parse_date(to, "to")

    device_status = {"normal": 0, "alarm": 0, "fault": 0, "masked": 0}
    devices = db.query(Device).all()
    for d in devices:
        key = d.status if d.status in device_status else "normal"
        device_status[key] += 1

    alarm_q = db.query(Alarm)
    if from_dt:
        alarm_q = alarm_q.filter(Alarm.trigger_at >= from_dt)
    if to_dt:
        alarm_q = alarm_q.filter(Alarm.trigger_at <= to_dt + timedelta(days=1))

    if from_dt and to_dt:
        start = from_dt
        days = max(1, (to_dt - from_dt).days + 1)
    elif from_dt:
        start = from_dt
        days = max(1, (utcnow().date() - from_dt.date()).days + 1)
    else:
        start = utcnow() - timedelta(days=29)
        days = 30
    trend_alarms = alarm_q.filter(Alarm.trigger_at >= start).all()
    by_date = {}
    for a in trend_alarms:
        day = a.trigger_at.strftime("%Y-%m-%d")
        by_date[day] = by_date.get(day, 0) + 1
    alarm_trend = [
        {"date": (start + timedelta(days=i)).strftime("%Y-%m-%d"), "count": by_date.get((start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(days)
    ]

    all_alarms = alarm_q.all()
    alarm_total = len(all_alarms)
    alarm_false = sum(1 for a in all_alarms if a.status == "confirmed_false")
    alarm_true = sum(1 for a in all_alarms if a.status == "confirmed_real")
    false_alarm_rate = round(alarm_false / alarm_total * 100, 1) if alarm_total else 0.0

    patrol_q = db.query(Patrol)
    if from_dt:
        patrol_q = patrol_q.filter(Patrol.scheduled_date >= from_dt.strftime("%Y-%m-%d"))
    if to_dt:
        patrol_q = patrol_q.filter(Patrol.scheduled_date <= to_dt.strftime("%Y-%m-%d"))
    patrol_total = patrol_q.count()
    patrol_done = patrol_q.filter(Patrol.status.in_(["normal", "abnormal"])).count()
    patrol_done_rate = round(patrol_done / patrol_total * 100, 1) if patrol_total else 0.0

    results = db.query(LinkageResult).all()
    total_results = len(results)
    success_results = sum(1 for r in results if r.status == "success")
    linkage_success_rate = round(success_results / total_results * 100, 1) if total_results else 0.0

    recent = alarm_q.options(joinedload(Alarm.device)).order_by(Alarm.id.desc()).limit(10).all()
    recent_alarms = [
        {
            "id": a.id,
            "device_name": a.device.name if a.device else None,
            "fire_type": a.fire_type,
            "trigger_at": a.trigger_at,
            "status": a.status,
        }
        for a in recent
    ]

    drill_q = db.query(Drill)
    if from_dt:
        drill_q = drill_q.filter(Drill.plan_date >= from_dt.strftime("%Y-%m-%d"))
    if to_dt:
        drill_q = drill_q.filter(Drill.plan_date <= to_dt.strftime("%Y-%m-%d"))

    return {
        "device_status": device_status,
        "alarm_trend": alarm_trend,
        "false_alarm_rate": false_alarm_rate,
        "patrol_done_rate": patrol_done_rate,
        "linkage_success_rate": linkage_success_rate,
        "alarm_total": alarm_total,
        "alarm_true": alarm_true,
        "alarm_false": alarm_false,
        "device_total": len(devices),
        "plan_total": db.query(Plan).count(),
        "drill_total": drill_q.count(),
        "emergency_total": db.query(Emergency).count(),
        "recent_alarms": recent_alarms,
    }


def _rows_for(data: str, db: Session, from_dt=None, to_dt=None):
    date_from = from_dt.strftime("%Y-%m-%d") if from_dt else None
    date_to = to_dt.strftime("%Y-%m-%d") if to_dt else None

    if data == "alarms":
        query = db.query(Alarm).options(joinedload(Alarm.device))
        if from_dt:
            query = query.filter(Alarm.trigger_at >= from_dt)
        if to_dt:
            query = query.filter(Alarm.trigger_at <= to_dt + timedelta(days=1))
        query = query.order_by(Alarm.id.desc())
        headers = ["ID", "设备编号", "设备名称", "火灾类型", "触发时间", "状态", "误报原因", "现场描述"]
        rows = []
        for a in query.all():
            rows.append(
                [
                    a.id,
                    a.device.device_no if a.device else "",
                    a.device.name if a.device else "",
                    a.fire_type,
                    a.trigger_at.strftime("%Y-%m-%d %H:%M:%S") if a.trigger_at else "",
                    a.status,
                    a.false_reason or "",
                    a.scene or "",
                ]
            )
        return headers, rows, "报警明细"
    elif data == "patrols":
        query = db.query(Patrol)
        if date_from:
            query = query.filter(Patrol.scheduled_date >= date_from)
        if date_to:
            query = query.filter(Patrol.scheduled_date <= date_to)
        query = query.order_by(Patrol.id.desc())
        headers = ["ID", "设备ID", "区域ID", "计划日期", "状态", "巡检人", "巡检时间", "结果", "建议"]
        rows = []
        for p in query.all():
            rows.append(
                [
                    p.id,
                    p.device_id,
                    p.area_id,
                    p.scheduled_date or "",
                    p.status,
                    p.patrol_by or "",
                    p.patrol_time.strftime("%Y-%m-%d %H:%M:%S") if p.patrol_time else "",
                    p.result or "",
                    p.suggest or "",
                ]
            )
        return headers, rows, "巡检记录"
    elif data == "drills":
        query = db.query(Drill)
        if date_from:
            query = query.filter(Drill.plan_date >= date_from)
        if date_to:
            query = query.filter(Drill.plan_date <= date_to)
        query = query.order_by(Drill.id.desc())
        headers = ["ID", "标题", "类型", "区域ID", "计划日期", "状态", "组织者", "评分", "评估", "总结"]
        rows = []
        for d in query.all():
            rows.append(
                [
                    d.id,
                    d.title,
                    d.drill_type or "",
                    d.area_id,
                    d.plan_date or "",
                    d.status,
                    d.organizer or "",
                    d.score if d.score is not None else "",
                    d.evaluate or "",
                    d.summary or "",
                ]
            )
        return headers, rows, "演练记录"
    raise HTTPException(status_code=400, detail="不支持的数据集")


def _filename(name: str, ext: str):
    return f"attachment; filename*=UTF-8''{quote(name)}.{ext}"


@router.get("/export")
def export(
    type: str = "excel",
    data: str = "alarms",
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleDependency(STATS_ROLE)),
):
    from_dt = _parse_date(from_, "from")
    to_dt = _parse_date(to, "to")
    headers, rows, label = _rows_for(data, db, from_dt, to_dt)

    if type == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(_sanitize_rows(rows))
        content = "\ufeff" + buffer.getvalue()
        return StreamingResponse(
            iter([content]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": _filename(label, "csv")},
        )

    if type == "excel":
        wb = Workbook()
        ws = wb.active
        ws.title = label
        ws.append(headers)
        for row in _sanitize_rows(rows):
            ws.append(row)
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return StreamingResponse(
            iter([bio.getvalue()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": _filename(label, "xlsx"),
            },
        )

    raise HTTPException(status_code=400, detail="type 必须为 excel 或 csv")