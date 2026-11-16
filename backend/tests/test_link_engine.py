"""联动引擎单测：execute_linkage 状态机与 get_matching_plan 匹配。"""
from app.link_engine import execute_linkage, get_matching_plan, _derive_run_status
from app.models import Plan, Area, LinkageResult
from app.auth import create_access_token


def _mk_plan(db_session, area_id, fire_type="other", actions=None, enabled=True):
    plan = Plan(
        name="单测预案",
        area_id=area_id,
        fire_type=fire_type,
        actions=actions if actions is not None else [
            {"action_type": "smoke_exhaust", "action_name": "启动排烟"},
            {"action_type": "fire_door", "action_name": "关闭防火门"},
        ],
        enabled=enabled,
    )
    db_session.add(plan)
    db_session.flush()
    return plan


def _owner(db_session):
    from app.models import User
    return db_session.query(User).filter(User.username == "duty").first()


def test_execute_full_success(db_session):
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id)
    run = execute_linkage(db_session, plan, owner_id=_owner(db_session).id, trigger_type="manual")
    db_session.refresh(run)
    assert run.status == "success"
    results = db_session.query(LinkageResult).filter(LinkageResult.run_id == run.id).all()
    assert len(results) == 2
    assert all(r.status == "success" for r in results)


def test_execute_empty_actions_failed(db_session):
    """空 actions -> run failed（修复：空动作分支恒真隐患）。"""
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id, actions=[])
    run = execute_linkage(db_session, plan, owner_id=_owner(db_session).id)
    db_session.refresh(run)
    assert run.status == "failed"
    results = db_session.query(LinkageResult).filter(LinkageResult.run_id == run.id).all()
    assert len(results) == 0


def test_execute_partial_failure(db_session):
    """部分动作失败 -> run partial。"""
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id, actions=[
        {"action_type": "fire_door", "action_name": "关闭防火门"},
        {"action_type": "broadcast", "action_name": "启动广播", "status": "failed"},
    ])
    run = execute_linkage(db_session, plan, owner_id=_owner(db_session).id)
    db_session.refresh(run)
    assert run.status == "partial"
    results = db_session.query(LinkageResult).filter(LinkageResult.run_id == run.id).all()
    assert len(results) == 2
    statuses = {r.status for r in results}
    assert statuses == {"success", "failed"}


def test_execute_all_failed(db_session):
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id, actions=[
        {"action_type": "fire_door", "action_name": "关闭防火门", "status": "failed"},
    ])
    run = execute_linkage(db_session, plan, owner_id=_owner(db_session).id)
    db_session.refresh(run)
    assert run.status == "failed"


def test_execute_none_plan_returns_none(db_session):
    assert execute_linkage(db_session, None, owner_id=1) is None


def test_derive_run_status_logic():
    class R:
        def __init__(self, status):
            self.status = status
    assert _derive_run_status([]) == "failed"
    assert _derive_run_status([R("success"), R("success")]) == "success"
    assert _derive_run_status([R("success"), R("failed")]) == "partial"
    assert _derive_run_status([R("failed"), R("failed")]) == "failed"


def test_get_matching_plan_exact_match(db_session):
    a1 = db_session.query(Area).order_by(Area.id)[0]
    a2 = db_session.query(Area).order_by(Area.id)[1]
    plan_elec = _mk_plan(db_session, a1.id, fire_type="electrical", actions=[])
    _mk_plan(db_session, a1.id, fire_type="oil", actions=[])
    _mk_plan(db_session, a2.id, fire_type="electrical", actions=[])

    matched = get_matching_plan(db_session, a1.id, "electrical")
    assert matched.id == plan_elec.id


def test_get_matching_plan_general_fallback(db_session):
    a = db_session.query(Area).order_by(Area.id)[2]
    general = _mk_plan(db_session, a.id, fire_type="ordinary", actions=[])
    matched = get_matching_plan(db_session, a.id, "oil")
    assert matched.id == general.id


def test_get_matching_plan_disabled_excluded(db_session):
    a = db_session.query(Area).order_by(Area.id)[3]
    _mk_plan(db_session, a.id, fire_type="electrical", enabled=False)
    assert get_matching_plan(db_session, a.id, "electrical") is None


def test_execute_records_trigger_type_and_owner(db_session):
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id)
    owner = _owner(db_session)
    run = execute_linkage(db_session, plan, alarm_id=999, owner_id=owner.id, trigger_type="auto")
    db_session.refresh(run)
    assert run.trigger_type == "auto"
    assert run.owner_id == owner.id
    assert run.alarm_id == 999


def test_execute_linkage_flush_only_rolls_back(db_session):
    """execute_linkage 只 flush 不 commit：异常回滚后不残留半成品 run（AL-28）。"""
    area = db_session.query(Area).order_by(Area.id).first()
    plan = _mk_plan(db_session, area.id)
    db_session.commit()
    execute_linkage(db_session, plan, owner_id=_owner(db_session).id, trigger_type="manual")
    db_session.rollback()
    assert db_session.query(LinkageResult).count() == 0
    from app.models import LinkageRun
    assert db_session.query(LinkageRun).count() == 0