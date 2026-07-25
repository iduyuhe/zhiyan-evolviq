"""P2 自进化层 —— 真实 runtime 端到端验证脚本。

用 ASGITransport 直打 FastAPI app（不触发 lifespan，单测级隔离），
覆盖：自反思生成候选 prompt → 审批 → 应用(热替换) → 回滚 → KG 事实提议/审批 → 偏好校准。
注意：应用会热替换 live `supply_chain` 单例的 system_prompt，验证后回滚，不影响其它用例。

用法：
    .venv/Scripts/python.exe scripts/verify_p2_evolution.py
退出码 0 = 全部通过。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from httpx import ASGITransport

from src.runtime.main import app


async def main() -> int:
    fails = []
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:

        # 1) 自反思：生成候选 prompt（无 LLM Key → 启发式，source=heuristic；无失败案例→none）
        r = await c.post("/evolution/reflect", json={"agent": "supply_chain"})
        if r.status_code != 200:
            fails.append(f"reflect 失败: {r.status_code} {r.text}")
            return _report(fails)
        body = r.json()
        vid = body["version_id"]
        print(f"[1] reflect        → status={body['status']} source={body['source']} v{body['version']} id={vid}")

        # 2) 列出版本，应有 1 条
        r = await c.get("/evolution/prompt-versions/supply_chain")
        if r.status_code != 200 or len(r.json()["versions"]) != 1:
            fails.append(f"list_versions 异常: {r.text}")
            return _report(fails)
        print(f"[2] list_versions  → 1 条候选")

        # 3) 审批通过
        r = await c.post(f"/evolution/prompt-versions/{vid}/approve")
        if r.status_code != 200 or r.json()["status"] != "approved":
            fails.append(f"approve 失败: {r.text}")
            return _report(fails)
        print(f"[3] approve       → approved")

        # 4) 应用（热替换 live 单例）
        r = await c.post(f"/evolution/prompt-versions/{vid}/apply")
        if r.status_code != 200 or r.json()["status"] != "applied":
            fails.append(f"apply 失败: {r.text}")
            return _report(fails)
        ra = await c.get("/evolution/prompt-versions/supply_chain/active")
        assert ra.json()["active"]["id"] == vid
        print(f"[4] apply         → active=√ 热替换生效")

        # 5) 回滚
        r = await c.post("/evolution/prompt-versions/supply_chain/rollback")
        if r.status_code != 200 or r.json()["status"] != "rolled_back":
            fails.append(f"rollback 失败: {r.text}")
            return _report(fails)
        print(f"[5] rollback      → √ 已还原上一版")

        # 6) KG 事实提议
        r = await c.post("/evolution/kg-facts/propose", json={
            "agent": "supply_chain", "subject": "MAT:MCU-001", "predicate": "可替代",
            "object": "MAT:MCU-002", "source": "验证脚本", "confidence": 0.9,
        })
        if r.status_code != 200 or r.json()["status"] != "draft":
            fails.append(f"kg propose 失败: {r.text}")
            return _report(fails)
        kid = r.json()["proposal"]["id"]
        print(f"[6] kg propose    → draft id={kid}")

        # 7) KG 事实审批（upsert 进图谱）
        r = await c.post(f"/evolution/kg-facts/{kid}/approve")
        if r.status_code != 200 or r.json()["status"] != "approved":
            fails.append(f"kg approve 失败: {r.text}")
            return _report(fails)
        print(f"[7] kg approve    → approved（已 upsert 图谱）")

        # 8) 偏好校准
        r = await c.get("/evolution/preference/supply_chain")
        if r.status_code != 200:
            fails.append(f"preference 失败: {r.text}")
            return _report(fails)
        cal = r.json()
        print(f"[8] preference    → verdict={cal['verdict']} approval_rate={cal['approval_rate']}")

    return _report(fails)


def _report(fails: list) -> int:
    print("\n" + "=" * 56)
    if fails:
        print("❌ P2 自进化验证失败：")
        for f in fails:
            print("  - " + f)
        return 1
    print("✅ P2 自进化端到端验证全部通过（reflect→approve→apply→rollback + KG + preference）")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
