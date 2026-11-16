from datetime import datetime
import os

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import (
    User,
    Area,
    Device,
    Plan,
    Drill,
    Patrol,
    Repair,
)

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

DEVICE_TYPE_NAMES = {
    "smoke": "烟感探测器",
    "temp": "温感探测器",
    "manual": "手动报警按钮",
    "hydrant": "消火栓",
    "sprinkler": "喷淋头",
    "smoke_exhaust": "排烟风机",
    "fire_door": "防火门",
    "emergency_light": "应急照明",
}

AREA_NAMES = [
    ("A区一层", "A座", "1层"),
    ("A区二层", "A座", "2层"),
    ("B区一层", "B座", "1层"),
    ("B区三层", "B座", "3层"),
    ("C区二层", "C座", "2层"),
    ("D区一层", "D座", "1层"),
]


def seed(db: Session):
    # 通过环境变量 FIRE_ALARM_SEED_DISABLED=1 显式关闭种子（生产可设为 1）。
    if os.getenv("FIRE_ALARM_SEED_DISABLED", "") == "1":
        return
    # 幂等：users 表非空（已有账号）时不再重复灌种子，保证重启/多实例不重复写入。
    if db.query(User).first():
        return

    # demo 账号密码可从环境变量覆盖，缺省回退 123456（保持本地 demo 可登录）。
    default_pwd = os.getenv("FIRE_ALARM_SEED_PASSWORD", "123456")
    users = [
        User(username="duty", password_hash=hash_password(default_pwd), real_name="值班员", role="duty", is_active=True),
        User(username="maintain", password_hash=hash_password(default_pwd), real_name="维保员", role="maintenance", is_active=True),
        User(username="admin", password_hash=hash_password(default_pwd), real_name="消防主管", role="supervisor", is_active=True),
    ]
    db.add_all(users)

    areas = []
    for name, building, floor in AREA_NAMES:
        area = Area(name=name, building=building, floor=floor)
        areas.append(area)
        db.add(area)
    db.flush()

    device_no = 1
    for area in areas:
        for idx, dtype in enumerate(DEVICE_TYPES):
            dev = Device(
                device_no=f"D-{device_no:03d}",
                name=f"{area.name}-{DEVICE_TYPE_NAMES[dtype]}{idx + 1}",
                device_type=dtype,
                area_id=area.id,
                x=round((idx % 4) * 5 + 10, 1),
                y=round((idx % 3) * 6 + 15, 1),
                status="normal",
                install_date="2024-01-01",
                remark="",
            )
            device_no += 1
            db.add(dev)
    db.flush()

    plans = [
        Plan(
            name="A区一层普通火灾联动预案",
            area_id=areas[0].id,
            fire_type="ordinary",
            enabled=True,
            actions=[
                {"action_type": "smoke_exhaust", "action_name": "启动排烟风机"},
                {"action_type": "fire_door", "action_name": "关闭防火门"},
                {"action_type": "emergency_light", "action_name": "启动应急照明"},
                {"action_type": "broadcast", "action_name": "启动疏散广播"},
            ],
        ),
        Plan(
            name="B区电气火灾联动预案",
            area_id=areas[2].id,
            fire_type="electrical",
            enabled=True,
            actions=[
                {"action_type": "fire_door", "action_name": "关闭防火门"},
                {"action_type": "emergency_light", "action_name": "启动应急照明"},
                {"action_type": "broadcast", "action_name": "启动疏散广播"},
            ],
        ),
        Plan(
            name="C区油烟火灾联动预案",
            area_id=areas[4].id,
            fire_type="oil",
            enabled=True,
            actions=[
                {"action_type": "smoke_exhaust", "action_name": "启动排烟风机"},
                {"action_type": "broadcast", "action_name": "启动疏散广播"},
            ],
        ),
        Plan(
            name="D区综合火灾联动预案",
            area_id=areas[5].id,
            fire_type="ordinary",
            enabled=True,
            actions=[
                {"action_type": "smoke_exhaust", "action_name": "启动排烟风机"},
                {"action_type": "emergency_light", "action_name": "启动应急照明"},
            ],
        ),
    ]
    db.add_all(plans)

    drills = [
        Drill(
            title="A区月度疏散演练",
            drill_type="疏散演练",
            area_id=areas[0].id,
            plan_date="2025-10-10",
            status="planned",
            organizer="消防主管",
            participants="全体人员",
            process="",
        ),
        Drill(
            title="B区灭火器使用演练",
            drill_type="灭火演练",
            area_id=areas[2].id,
            plan_date="2025-09-15",
            status="done",
            organizer="消防主管",
            participants="义务消防队",
            process="讲解灭火器使用并实操",
            score=92,
            evaluate="全员掌握灭火器操作",
            summary="演练顺利，达到预期",
        ),
        Drill(
            title="C区消防报警联动测试",
            drill_type="联动测试",
            area_id=areas[4].id,
            plan_date="2025-11-01",
            status="planned",
            organizer="维保员",
            participants="维保组",
            process="",
        ),
    ]
    db.add_all(drills)

    some_device = db.query(Device).first()
    patrols = [
        Patrol(
            device_id=some_device.id,
            area_id=some_device.area_id,
            scheduled_date="2025-09-26",
            status="pending",
            patrol_by="维保员",
        ),
        Patrol(
            device_id=some_device.id,
            area_id=some_device.area_id,
            scheduled_date="2025-09-20",
            status="normal",
            patrol_by="维保员",
            result="设备运行正常",
        ),
    ]
    db.add_all(patrols)

    repairs = [
        Repair(
            device_id=some_device.id,
            title="设备例行保养",
            description="例行维护保养",
            creator="维保员",
            status="in_progress",
        ),
    ]
    db.add_all(repairs)

    db.commit()