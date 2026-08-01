"""杜特第0号真实客户·真实数据信号源钩子（P1-4 北极星起跳）

铁律①：外部系统(OPC-UA/ERP/MES)实测暂缓，本钩子仅消费杜特自身已披露/已决策的真实业务上下文
（data/dute/real_signals.json），作为北极星「决策实时化率」真实率(Real)的起跳原料。
标记为 real_time=True，区别于 ZHIYAN_DEMO_DATA 演示态；真实率与 demo 率严格分离、不混入。

钩子可扩展性：未来真实签约客户接入时，把本模块的「从 JSON 读取」替换为「从客户数据源连接器读取」，
其余（record_decision_realization + north_star_report）指标内核链路完全复用，无需改动内核。
"""

from __future__ import annotations

import json
import logging
import os

from src.runtime.core.metrics import metrics

logger = logging.getLogger(__name__)

SIGNAL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "dute", "real_signals.json",
)
SEED_PREFIX = "dute-real-"


def seed_dute_real() -> dict:
    """注入杜特真实业务信号，使北极星真实率从 0% 起跳。幂等、可开关。"""
    if os.environ.get("ZHIYAN_DUTE_REAL", "1") != "1":
        logger.info("⏭️ 杜特真实信号源未启用（ZHIYAN_DUTE_REAL!=1），跳过")
        return {"loaded": False, "reason": "disabled"}
    if metrics.already_seeded(SEED_PREFIX):
        logger.info("✅ 杜特真实信号源已注入过（幂等跳过，跨重启不重复累计）")
        return {"loaded": False, "reason": "already_seeded"}
    if not os.path.exists(SIGNAL_FILE):
        logger.warning("⚠️ 杜特真实信号清单缺失：%s", SIGNAL_FILE)
        return {"loaded": False, "reason": "file_not_found"}
    try:
        with open(SIGNAL_FILE, encoding="utf-8") as f:
            spec = json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.warning("⚠️ 杜特真实信号清单加载失败：%s", e)
        return {"loaded": False, "reason": str(e)}

    tenant = spec.get("tenant_id", "dute")
    total = realized = 0
    for s in spec.get("signals", []):
        did = s.get("id") or f"{SEED_PREFIX}{total:03d}"
        is_realized = bool(s.get("realized", True))
        # real_time=True → 计入北极星真实率；与 demo 演示态(DEMO_DATA)严格分离
        metrics.record_decision_realization(
            decision_id=did, realized=is_realized, real_time=True, tenant=tenant,
        )
        total += 1
        realized += 1 if is_realized else 0

    summary = {
        "loaded": True, "tenant": tenant, "total": total,
        "realized": realized, "real_time": True,
    }
    logger.info(f"🟢 杜特真实信号源已注入（北极星真实率起跳）：{summary}")
    return summary
