"""务实化验证脚本：端到端跑通 8 个 Agent，确认无随机、可复现、返回 actions_taken。

运行方式（在 zhiyan 目录下）：
    python verify_wushihua.py
"""
import asyncio
import json
import sys

from src.runtime.agent.router import execute_by_agent, ROUTING_RULES

# 每个 Agent 的代表性目标（关键词需命中路由规则）
CASES = [
    ("quality_trace", "28nm晶圆边缘颗粒污染超标客诉追溯根因"),
    ("ipc_standard", "BGA焊球空洞多少算缺陷？"),
    ("oee_optimizer", "分析SMT产线OEE效率与六大损失"),
    ("smt_changeover", "PCB-A-v3.2 切换到 PCB-C-v2.0 的换线计划"),
    ("aoi_judge", "SMT-L01 AOI误报率优化复判"),
    ("dfm_check", "全板DFM可制造性设计检查"),
    ("bom_selector", "STM32F407VGT6 选型替代料推荐"),
    ("eco_change", "ECO-2026-045 MCU切换影响分析"),
]


async def main():
    failures = []
    for agent_name, goal in CASES:
        try:
            r1 = await execute_by_agent(agent_name, goal)
            r2 = await execute_by_agent(agent_name, goal)
        except Exception as e:
            failures.append((agent_name, f"EXCEPTION: {type(e).__name__}: {e}"))
            continue

        # 1) 必须返回 actions_taken 列表
        at = r1.get("actions_taken")
        if not isinstance(at, list):
            failures.append((agent_name, f"actions_taken 缺失/类型错误: {type(at)}"))

        # 2) 可复现：两次调用结果应完全一致（排除不可序列化字段）
        def compact(d):
            return json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)
        if compact(r1) != compact(r2):
            failures.append((agent_name, "结果不可复现（两次调用不一致）"))

        # 3) summary 必须存在
        if not r1.get("summary"):
            failures.append((agent_name, "summary 缺失"))

        is_fail = any(a == agent_name for a, _ in failures)
        print(f"[{'✅' if not is_fail else '❌'}] {agent_name:14s} "
              f"summary={r1.get('summary','')[:42]}... actions={len(at) if isinstance(at,list) else 0}")

    print("\n=== 路由规则覆盖检查 ===")
    print(f"路由规则数: {len(ROUTING_RULES)}")

    if failures:
        print("\n❌ 失败项:")
        for name, msg in failures:
            print(f"  - {name}: {msg}")
        sys.exit(1)
    else:
        print("\n✅ 全部 8 个 Agent 务实化验证通过（无随机、可复现、含 actions_taken）")


if __name__ == "__main__":
    asyncio.run(main())
