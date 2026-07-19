"""T3 验证脚本：经真实 HTTP API 跑通供应链齐套率 ROI 闭环。

流程：建会话(supply_chain) → 审批 → 取结果 → 断言 metrics 闭环 → 校验落库。
离线：用临时 SQLite（ZHIYAN_DB_URL 覆盖），不依赖外部 PostgreSQL。
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

DB_PATH = os.path.join(tempfile.gettempdir(), "zhiyan_t3_verify.db")
os.environ["ZHIYAN_DB_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"

import httpx
from sqlalchemy import select, text

from src.common import db
from src.runtime.main import app


async def main():
    db.configure_db()
    await db.init_db()
    print(f"DB 模式: {db.db_mode} | 可用: {db.db_available}")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1) 建会话（供应链目标）
        r = await client.post("/sessions", json={"goal": "检查BOM-SMIC-28nm-Logic齐套率并提升到85%"})
        sid = r.json()["session_id"]
        print(f"会话已建: {sid[:8]}... | agent={r.json().get('agent')}")

        # 2) 审批执行
        r = await client.post(f"/sessions/{sid}/approve", json={"approved": True})
        assert r.status_code == 200, r.text
        result = r.json()["result"]

        # 3) 断言 ROI 闭环
        m = result["metrics"]
        print("\n===== 齐套率 ROI 闭环 =====")
        print(f"齐套率:  {m['kitting_rate_before']}%  →  {m['kitting_rate_after']}%  ({m['improvement_pp']:+}pp)")
        print(f"风险项:  {m['risk_items_before']}  →  {m['risk_items_after']}")
        print(f"缺料量:  {m['shortage_qty_before']}  →  {m['shortage_qty_after']} pcs")
        print(f"交期率:  {m['delivery_accuracy_before']}%  →  {m['delivery_accuracy_after']}%")
        print(f"摘要:    {m['roi_summary']}")

        assert m["kitting_rate_before"] < m["kitting_rate_after"], "闭环不成立"
        assert result["completeness_pct"] == m["kitting_rate_after"]

        # 4) 校验落库（AgentSession 含 metrics JSON）
        from src.runtime.persistence import get_session as db_get_session
        row = await db_get_session(sid)
        assert row is not None, "会话未落库"
        res_json = row["result"]
        assert isinstance(res_json, dict) and "metrics" in res_json, "落库结果缺 metrics"
        assert res_json["metrics"]["kitting_rate_after"] == m["kitting_rate_after"]
        print("\n✅ 落库校验通过：AgentSession.result.metrics 已持久化")

        # 5) DB 查询接口
        r = await client.get("/system/db")
        print(f"GET /system/db -> mode={r.json()['mode']}, available={r.json()['available']}")

        print("\n🎯 T3 验证通过：供应链齐套率 ROI 闭环（基准→承诺）端到端打通，且已落库。")


if __name__ == "__main__":
    asyncio.run(main())
