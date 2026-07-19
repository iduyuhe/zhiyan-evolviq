"""演示效果信号种子——让「按效果调参」在无真实流量时也能跑出可信的效果信号与建议。

加载方式：仅当环境变量 ZHIYAN_DEMO_DATA=1 时由 main.lifespan 调用 seed_demo_data()。
数据来源：data/seed/metrics_demo.json（11 个 Agent 的演示动作统计与介入决策）。

事实锚点铁律：本模块仅注入 metrics 与介入队列的演示统计，绝不改写任何业务数字或动作。
"""

from __future__ import annotations

import json
import logging
import os

from src.runtime.core.authorization import PlannedAction
from src.runtime.core.intervention import Intervention, intervention_queue
from src.runtime.core.metrics import metrics

logger = logging.getLogger(__name__)

SEED_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "seed", "metrics_demo.json",
)


def _demo_action(agent: str) -> PlannedAction:
    """构造一个最小可演示的 PlannedAction（仅用于填充介入队列统计，不被执行）。"""
    return PlannedAction(
        type="auto_action",
        category="",
        price_delta_pct=0.0,
        qty=0,
        confidence=0.9,
        detail=f"[demo] {agent} intervention",
        session_id=f"demo-{agent}",
    )


def seed_demo_data() -> dict:
    """从 metrics_demo.json 注入演示效果信号。返回注入摘要。"""
    if not os.path.exists(SEED_FILE):
        logger.warning("⚠️ 演示种子文件不存在，跳过：%s", SEED_FILE)
        return {"loaded": False, "reason": "file_not_found"}
    try:
        with open(SEED_FILE, encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:
        logger.warning("⚠️ 演示种子加载失败：%s", e)
        return {"loaded": False, "reason": str(e)}

    summary: dict = {"agents": 0, "sessions": 0, "interventions": 0}
    for a in spec.get("agents", []):
        agent = a["agent"]
        total = int(a.get("total", 0))
        auto = int(a.get("auto", 0))
        human = total - auto
        # 1) 效果指标：按 Agent 聚合的自主/人工动作（支撑 per_agent_report + effect_report）
        metrics.record(
            session_id=f"demo-{agent}",
            agent=agent,
            total=total,
            auto=auto,
            human=human,
        )
        summary["sessions"] += 1
        # 2) 介入队列：注入已决策的介入事项，驱动批准率/驳回统计（effect_signals 读此处）
        boundary_id = f"ab-{agent}-default"
        for _ in range(int(a.get("approved", 0))):
            ivt = Intervention(
                session_id=f"demo-{agent}", agent=agent,
                action=_demo_action(agent), reason="[demo] 人工批准", boundary_id=boundary_id,
            )
            intervention_queue.push(ivt)
            intervention_queue.decide(ivt.id, approved=True)
            metrics.record_decision(ivt.id, approved=True)
            summary["interventions"] += 1
        for _ in range(int(a.get("rejected", 0))):
            ivt = Intervention(
                session_id=f"demo-{agent}", agent=agent,
                action=_demo_action(agent), reason="[demo] 人工驳回", boundary_id=boundary_id,
            )
            intervention_queue.push(ivt)
            intervention_queue.decide(ivt.id, approved=False)
            metrics.record_decision(ivt.id, approved=False)
            summary["interventions"] += 1

    summary["agents"] = len(spec.get("agents", []))
    summary["loaded"] = True
    logger.info(f"🎬 演示效果信号已注入：{summary}")
    return summary
