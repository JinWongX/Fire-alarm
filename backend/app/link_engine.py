from datetime import datetime

from .models import LinkageRun, LinkageResult, Plan


def _derive_run_status(results) -> str:
    """由联动结果的实际状态推导 run 状态，避免空动作 / 部分失败时分支恒真。"""
    total = len(results)
    if total == 0:
        return "failed"
    success = sum(1 for r in results if r.status == "success")
    if success == total:
        return "success"
    if success > 0:
        return "partial"
    return "failed"


def execute_linkage(db, plan: Plan, alarm_id=None, owner_id=None, trigger_type="auto"):
    """对 plan.actions 逐条生成 linkage_result 成功记录，汇总 run 状态。

    只 flush 不 commit：由调用方在同一事务内提交，保证异常时整事务回滚、
    不残留半成品 run。
    """
    if plan is None:
        return None
    run = LinkageRun(
        plan_id=plan.id,
        alarm_id=alarm_id,
        owner_id=owner_id,
        trigger_type=trigger_type,
        status="success",
    )
    db.add(run)
    db.flush()

    for action in plan.actions or []:
        action_type = action.get("action_type", "") if isinstance(action, dict) else getattr(action, "action_type", "")
        action_name = action.get("action_name", "") if isinstance(action, dict) else getattr(action, "action_name", "")
        failed = (
            action.get("status") == "failed"
            if isinstance(action, dict)
            else getattr(action, "status", "") == "failed"
        )
        result = LinkageResult(
            run_id=run.id,
            action_type=action_type,
            action_name=action_name,
            status="failed" if failed else "success",
            detail="联动执行失败" if failed else "联动执行成功",
        )
        db.add(result)

    db.flush()
    results = db.query(LinkageResult).filter(LinkageResult.run_id == run.id).all()
    run.status = _derive_run_status(results)

    db.flush()
    return run


def get_matching_plan(db, area_id, fire_type):
    """按 区域 + 火灾类型 匹配启用的预案。"""
    plans = (
        db.query(Plan)
        .filter(Plan.enabled == True, Plan.area_id == area_id)
        .all()
    )
    exact = next((p for p in plans if p.fire_type == fire_type), None)
    if exact:
        return exact
    general = next((p for p in plans if p.fire_type in (None, "", "ordinary")), None)
    return general or (plans[0] if plans else None)