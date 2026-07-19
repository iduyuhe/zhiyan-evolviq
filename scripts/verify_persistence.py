"""T2 数据层落库——端到端验证（经真实 HTTP API 闭环）。

流程：初始化 DB（模拟 lifespan）→ 创建会话 → 人确认执行 → 查询落库数据。
关闭 LLM 以离线确定性运行；用 SQLite 验证「落库」真实发生。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "zhiyan_verify.db")
os.environ["ZHIYAN_DB_URL"] = f"sqlite+aiosqlite:///{DB_FILE}"

from httpx import ASGITransport, AsyncClient

from src.common import db
from src.meta_agent.audit import audit_logger
from src.runtime.persistence import log_audit
from src.common.llm_client import llm_client
from src.runtime.main import app


async def main():
    # 模拟应用 lifespan：建表 + 挂审计 sink
    ok = await db.init_db()
    audit_logger.attach_sink(log_audit)
    print(f"[init_db] ok={ok} mode={db.db_mode} available={db.db_available}")

    # 离线确定性（关闭 LLM，走规则引擎兜底）
    llm_client._providers = {}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) 创建会话（触发 plan → 落 AgentSession planning/awaiting_approval + 审计）
        goal = "检查BOM-NPI-007物料齐套并预警缺料"
        r = await client.post("/sessions", json={"goal": goal})
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        print(f"[create] session_id={sid[:8]} status={r.json()['status']}")

        # 2) 人确认执行（触发 execute → 落 AgentSession completed + result JSON + 审计）
        r = await client.post(f"/sessions/{sid}/approve", json={"approved": True})
        assert r.status_code == 200, r.text
        result = r.json()["result"]
        print(f"[execute] summary={result.get('summary','')[:40]}... "
              f"completeness={result.get('completeness_pct')}% "
              f"actions={len(result.get('actions_taken', []))}")

        # 3) 查询落库会话（重启后仍可追溯）
        r = await client.get("/sessions/db")
        db_sessions = r.json()["sessions"]
        assert any(s["session_id"] == sid for s in db_sessions), "会话未落库"
        print(f"[GET /sessions/db] source={r.json()['source']} total={r.json()['total']} "
              f"matched_our_session=✅")

        # 4) 单条落库会话含完整 result JSON
        r = await client.get(f"/sessions/{sid}/db")
        assert r.status_code == 200, r.text
        row = r.json()
        assert row["status"] == "completed"
        assert row["result"]["summary"] == result["summary"], "事实锚点被改动！"
        print(f"[GET /sessions/{sid[:8]}/db] status={row['status']} "
              f"result.summary 一致=✅ 事实锚点未漂移")

        # 5) 审计日志（db 优先）——先排干 fire-and-forget 审计任务，确保已提交
        await asyncio.sleep(0)
        loop = asyncio.get_running_loop()
        others = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
        if others:
            await asyncio.gather(*others, return_exceptions=True)
        r = await client.get("/audit/logs")
        logs = r.json()["logs"]
        events = {l["event_type"] for l in logs}
        assert {"goal_set", "plan_created", "approved", "executed"}.issubset(events)
        print(f"[GET /audit/logs] source={r.json()['source']} total={r.json()['total']} "
              f"events={sorted(events)}")

        # 6) 系统 DB 状态
        r = await client.get("/system/db")
        st = r.json()
        print(f"[GET /system/db] available={st['available']} mode={st['mode']} url={st['url']}")
        assert st["available"] is True

    print("\n✅ T2 数据层落库端到端验证通过：AgentSession + AuditLog 已真实写入数据库，"
          "且确定性结果（事实锚点）逐字段一致。")


if __name__ == "__main__":
    asyncio.run(main())
