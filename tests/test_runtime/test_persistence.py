"""T2 数据层落库测试——AgentSession + AuditLog 入库，事实锚点不被改，且优雅降级不破管。

设计：本测试离线运行（关闭 LLM），用临时 SQLite 库，专注验证「落库」本身。
审计日志经 fire-and-forget sink 落库，查询前排干事件循环确保任务已提交。
"""

import asyncio
import os
import uuid

import pytest


async def _drain_audit_tasks():
    """排干当前事件循环中由审计 sink 派发的待提交任务。"""
    await asyncio.sleep(0)
    loop = asyncio.get_running_loop()
    others = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    if others:
        await asyncio.gather(*others, return_exceptions=True)


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    from src.common import db
    from sqlalchemy import delete

    from src.runtime.models.agent_session import AgentSession, AuditLog
    from src.meta_agent.audit import audit_logger
    from src.runtime.persistence import log_audit
    from src.common.llm_client import llm_client

    # 用临时 SQLite 库，避免依赖外部 PostgreSQL
    os_environ_backup = os.environ.get("ZHIYAN_DB_URL")
    os.environ["ZHIYAN_DB_URL"] = f"sqlite+aiosqlite:///{tmp_path / 'persist.db'}"

    db.configure_db()
    await db.init_db()
    # 清空相关表，保证测试独立
    async with db.async_session() as s:
        await s.execute(delete(AuditLog))
        await s.execute(delete(AgentSession))
        await s.commit()

    audit_logger.attach_sink(log_audit)
    llm_providers_was = dict(llm_client._providers)
    llm_client._providers = {}  # 离线确定性：available -> False

    yield

    llm_client._providers = llm_providers_was
    audit_logger.attach_sink(None)
    if os_environ_backup is None:
        os.environ.pop("ZHIYAN_DB_URL", None)
    else:
        os.environ["ZHIYAN_DB_URL"] = os_environ_backup


@pytest.mark.asyncio
async def test_session_and_audit_persisted():
    from src.runtime.agent.engine import AgentEngine
    from src.runtime.persistence import get_session, get_audit_logs

    engine = AgentEngine()
    sid = str(uuid.uuid4())
    goal = "检查BOM-NPI-007物料齐套"

    await engine.plan(sid, goal)
    result = await engine.execute(sid)
    await _drain_audit_tasks()

    # 1) AgentSession 已落库
    row = await get_session(sid)
    assert row is not None, "AgentSession 应已落库"
    assert row["goal"] == goal
    assert row["status"] == "completed"
    assert isinstance(row["result"], dict)

    # 2) 事实锚点：落库的 result 与确定性执行结果逐字段一致（不被落库过程改动）
    assert row["result"].get("summary") == result.get("summary")
    assert row["result"].get("completeness_pct") == result.get("completeness_pct")
    assert row["result"].get("actions_taken") == result.get("actions_taken")

    # 3) 审计日志入库（事件齐全）
    logs = await get_audit_logs(session_id=sid)
    events = {l["event_type"] for l in logs}
    assert {"goal_set", "plan_created", "approved", "executed"}.issubset(events)


@pytest.mark.asyncio
async def test_audit_logs_queryable_after_session():
    from src.runtime.agent.engine import AgentEngine
    from src.runtime.persistence import get_audit_logs, list_sessions

    engine = AgentEngine()
    sid = str(uuid.uuid4())
    await engine.plan(sid, "帮我做良率分析")
    await engine.execute(sid)
    await _drain_audit_tasks()

    logs = await get_audit_logs()
    assert any(l["session_id"] == sid for l in logs)

    sessions = await list_sessions()
    assert any(s["session_id"] == sid for s in sessions)


@pytest.mark.asyncio
async def test_graceful_degradation_when_db_down():
    """db 不可用时，execute 仍返回确定性结果，绝不抛异常、不破管。"""
    from src.common import db
    from src.runtime.agent.engine import AgentEngine

    db.db_available = False
    try:
        engine = AgentEngine()
        sid = str(uuid.uuid4())
        await engine.plan(sid, "检查BOM-NPI-007物料齐套")
        result = await engine.execute(sid)
        assert isinstance(result, dict)
        assert "summary" in result
    finally:
        db.db_available = True

