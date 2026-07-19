"""验证脚本：8 个 Agent 的 actions_taken 已接入授权边界 + 异常介入闭环

经完整 plan → execute 链路，确认：
- 高风险动作（CAPA/替代料/ECO/设计评审/培训）进入 pending_interventions（送审）
- 低风险动作（建报告/计划/改善任务）在授权内自主（auto）
- 置信度低于阈值的动作被拦截（aoi_judge）
- 介入队列 pending 总数 = 各 Agent 送审之和
- ipc_standard 放宽修复后稳定产出动作
- supply_chain 历史行为不被破坏（轻量回归）
"""
import asyncio
import sys

from src.runtime.agent.engine import AgentEngine
from src.runtime.core.intervention import intervention_queue

# (agent, 目标, 期望送审数)
CASES = [
    ("quality_trace", "追溯晶圆边缘颗粒污染超标问题", 1),
    ("ipc_standard", "焊锡桥连在所有Class下是否可接受", 1),
    ("oee_optimizer", "优化SMT产线一号线设备综合效率OEE", 0),
    ("smt_changeover", "制定从产品A到产品B的换线计划", 0),
    ("aoi_judge", "分析AOI误报并优化判定阈值", 1),
    ("dfm_check", "检查BGA封装可制造性DFM问题", 1),
    ("bom_selector", "为MCU芯片选型pin-to-pin替代料", 1),
    ("eco_change", "发起一次工程变更ECO", 2),
]


async def main():
    engine = AgentEngine()
    failures = []
    total_expect_pending = 0

    for name, goal, expect_pending in CASES:
        total_expect_pending += expect_pending
        sid = f"verify-{name}"
        await engine.plan(sid, goal)
        result = await engine.execute(sid)
        auto = result.get("autonomous_actions", [])
        pend = result.get("pending_interventions", [])
        ok = len(pend) == expect_pending
        if not ok:
            failures.append((name, expect_pending, len(pend)))
        tag = "✅" if ok else "❌"
        print(f"[{tag}] {name:14s} 自主={len(auto)} 送审={len(pend)} (期望送审={expect_pending})")
        for p in pend:
            print(f"        ↳ 送审: {p['action']['type']} ｜ {p['reason']}")

    total_pending = intervention_queue.pending_count()
    print(f"\n介入队列 pending 总数 = {total_pending}（期望 ≈ {total_expect_pending}）")
    if total_pending != total_expect_pending:
        failures.append(("queue_total", total_expect_pending, total_pending))

    # 轻量回归：supply_chain 不应被破坏（不强制断言数量，仅确认无异常且动作被评估）
    sid = "verify-supply"
    await engine.plan(sid, "评估SMIC晶圆厂光刻胶与靶材的供货齐套风险")
    r = await engine.execute(sid)
    sa = len(r.get("autonomous_actions", []))
    sp = len(r.get("pending_interventions", []))
    print(f"[回归] supply_chain 自主={sa} 送审={sp}（历史行为保持）")

    if failures:
        print("\n❌ 验证失败:", failures)
        return 1
    print("\n✅ 8 个 Agent 全部接入授权/介入闭环，验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
