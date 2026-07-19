"""V1-4 控制台策略调参——端到端验证（经真实 HTTP API 驱动 app）

不依赖 lifespan：策略 API 直接读全局单例（authorization/metrics/intervention_queue），
与既有 /auth/boundaries 共用同一授权引擎，调参即改运行时。
"""

import sys
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, "e:/agent_industry/zhiyan")

from src.runtime.main import app

PASS = "✅"
FAIL = "❌"


async def main():
    failures = 0
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:

        # 1) 控制台面板：聚合 current + effect + suggestions
        r = await c.get("/strategy")
        if r.status_code != 200:
            print(f"{FAIL} GET /strategy -> {r.status_code}")
            failures += 1
        else:
            d = r.json()
            agents = {x["agent"] for x in d["current"]}
            print(f"{PASS} GET /strategy 面板: {len(agents)} 个 Agent 旋钮, "
                  f"效果信号 {len(d['effect_signals'])} 项, 建议 {len(d['suggestions'])} 条")
            if len(agents) < 11:
                print(f"{FAIL} Agent 数量不足 11")
                failures += 1

        # 2) 效果驱动建议接口
        r = await c.get("/strategy/suggestions")
        if r.status_code != 200 or "suggestions" not in r.json():
            print(f"{FAIL} GET /strategy/suggestions")
            failures += 1
        else:
            print(f"{PASS} GET /strategy/suggestions: 目标自主率 "
                  f"{r.json()['target_autonomous_rate']}, 建议 {len(r.json()['suggestions'])} 条")

        # 3) 调参真正改写运行时边界（supply_chain 置信阈值 0.8 -> 0.72）
        before = (await c.get("/auth/boundaries/agent/supply_chain")).json()["boundary"]["confidence_threshold"]
        r = await c.post("/strategy/tune", json={
            "agent": "supply_chain", "param": "confidence_threshold",
            "value": 0.72, "reason": "验证：主动放权",
        })
        if r.status_code != 200 or r.json().get("new") != 0.72:
            print(f"{FAIL} POST /strategy/tune 未生效: {r.status_code} {r.text}")
            failures += 1
        else:
            after = (await c.get("/auth/boundaries/agent/supply_chain")).json()["boundary"]["confidence_threshold"]
            print(f"{PASS} POST /strategy/tune: supply_chain 置信阈值 {before} → {after}（运行时已改写）")
            if after != 0.72:
                print(f"{FAIL} 运行时边界未更新")
                failures += 1

        # 4) 夹紧 + 错误参数
        r = await c.post("/strategy/tune", json={
            "agent": "supply_chain", "param": "confidence_threshold",
            "value": 0.01, "reason": "越界夹紧",
        })
        clamped = r.json().get("new")
        bad = await c.post("/strategy/tune", json={
            "agent": "supply_chain", "param": "bogus", "value": 1,
        })
        miss = await c.post("/strategy/tune", json={
            "agent": "ghost", "param": "confidence_threshold", "value": 0.8,
        })
        ok = (clamped == 0.50) and (bad.status_code == 400) and (miss.status_code == 404)
        print(f"{PASS if ok else FAIL} 夹紧=0.50 / 非法参数=400 / 未知Agent=404"
              f" (clamped={clamped}, bad={bad.status_code}, miss={miss.status_code})")
        if not ok:
            failures += 1

        # 5) 审计轨迹
        h = (await c.get("/strategy/history")).json()
        print(f"{PASS} GET /strategy/history: 共 {h['total']} 条调参记录"
              + (f"，最新={h['history'][0]['agent']}.{h['history'][0]['param']}" if h['total'] else ""))
        if h["total"] < 2:
            print(f"{FAIL} 审计轨迹不足")
            failures += 1

        # 还原 supply_chain 阈值
        await c.post("/strategy/tune", json={
            "agent": "supply_chain", "param": "confidence_threshold",
            "value": before, "reason": "验证：还原",
        })

    print()
    if failures == 0:
        print(f"{PASS} V1-4 控制台策略调参：全部验证通过")
        return 0
    print(f"{FAIL} V1-4 验证失败：{failures} 项")
    return 1


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(main()))
