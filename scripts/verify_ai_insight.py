"""Task #49 验证：LLM 决策辅助下沉到各 Agent 执行阶段。

验证两件事：
1. execute() 后 result["ai_insight"] 是非空字符串且 ai_insight_source == "llm"（LLM 实际生效）
2. 事实锚点未被破坏：在同一次执行内，_generate_insight 前后确定性字段完全一致
   （LLM 只写 ai_insight / ai_insight_source，绝不触碰任何确定性字段）。

关键：事实锚点必须在【同一次执行内】比对。若跨两次独立执行比对会误报——因为
Intervention 每次生成新的 uuid id 和 datetime 时间戳，属于正常非确定性，与 LLM 无关。
故此处用子类在 _generate_insight 调用前深拷贝快照，执行后逐字段比对。
"""

import asyncio
import copy
import sys

sys.path.insert(0, "E:/agent_industry/zhiyan")

from src.common.llm_client import llm_client
from src.runtime.agent.engine import AgentEngine
from src.runtime.agent.router import route_goal

CASES = [
    ("供应链缺料齐套检查：请检查本周硅片、光刻胶物料齐套率并给出缺料预警", "supply_chain"),
    ("客诉根因追溯：某批次产品客诉异常，请做根因分析和追溯", "quality_trace"),
    ("产线 OEE 优化：请监控产线综合效率并定位六大损失", "oee_optimizer"),
]


class SnapshotEngine(AgentEngine):
    """在 _generate_insight 调用前对 result 做深拷贝快照（排除 insight 键），
    执行后即可逐字段比对，证明 LLM 未篡改任何确定性事实。"""

    def __init__(self):
        super().__init__()
        self.pre_snapshot: dict | None = None

    async def _generate_insight(self, agent_name, goal, result, autonomous_actions, pending_interventions):
        self.pre_snapshot = {
            k: copy.deepcopy(v)
            for k, v in result.items()
            if k not in ("ai_insight", "ai_insight_source")
        }
        return await super()._generate_insight(
            agent_name, goal, result, autonomous_actions, pending_interventions
        )


async def main():
    print("=" * 72)
    print(f"LLM 可用性: available={llm_client.available}")
    print("=" * 72)

    rows = []
    all_ok = True

    for goal, expect_agent in CASES:
        routed = route_goal(goal)
        print(f"\n▶ 目标: {goal[:40]}...")
        print(f"  路由 Agent: {routed} (期望 {expect_agent})")

        engine = SnapshotEngine()
        sid = "verify_" + str(id(goal))
        await engine.plan(sid, goal)
        result = await engine.execute(sid)

        insight = result.get("ai_insight")
        source = result.get("ai_insight_source")

        # 1) LLM 生效检查
        insight_ok = bool(insight) and isinstance(insight, str) and source == "llm"

        # 2) 事实锚点检查：同一次执行内，insight 生成前后确定性字段逐字段一致
        pre = engine.pre_snapshot or {}
        post = {k: v for k, v in result.items() if k not in ("ai_insight", "ai_insight_source")}
        drift = [k for k in pre if pre.get(k) != post.get(k)]
        added = [k for k in post if k not in pre]  # 只允许新增 insight 键（已排除）
        anchor_ok = (not drift) and (not added)

        status = "✅" if (insight_ok and anchor_ok) else "❌"
        if not (insight_ok and anchor_ok):
            all_ok = False

        print(f"  ai_insight_source = {source}")
        print(f"  ai_insight 非空 = {bool(insight)} (长度 {len(insight or '')})")
        print(f"  事实锚点未漂移 = {anchor_ok}"
              + (f" ⚠️ 漂移: {drift}" if drift else "")
              + (f" ⚠️ 多余新增: {added}" if added else ""))
        if insight:
            preview = insight.strip().replace("\n", " ")[:110]
            print(f"  insight 预览: {preview}...")

        rows.append((routed, source, bool(insight), anchor_ok, status))

    print("\n" + "=" * 72)
    print(f"{'Agent':<16}{'source':<8}{'insight':<9}{'事实锚点':<10}{'结果'}")
    print("-" * 72)
    for agent, source, has_insight, anchor_ok, status in rows:
        print(f"{agent:<16}{(source or 'none'):<8}{str(has_insight):<9}{str(anchor_ok):<12}{status}")
    print("=" * 72)
    print("总体: " + ("✅ 全部通过" if all_ok else "❌ 存在失败"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
