"""v27.0 产业链智能体联邦 —— 跨企业供应链协同

在 v24.0 联邦学习（KG 模式聚合）基础上，上一阶：
- 跨企业供应链目标共享（多企业 Agent 协同）
- 跨企业风险聚合（匿名化供应链风险视图）
- 联合排产与共担风险

设计原则：
- 去标识化：不暴露具体企业名、价格、合同条款
- 目标导向：只共享"目标/约束"级别信息，不共享业务数据
- 可选参与：企业可选择加入/退出特定协同
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FederatedSupplyChain:
    """产业链智能体联邦 —— 跨企业供应链协同核心。"""

    def __init__(self):
        # 共享目标池
        self._shared_goals: list[dict] = []
        # 跨企业风险记录
        self._cross_risks: list[dict] = []
        # 联合计划
        self._joint_plans: list[dict] = []
        # 参与企业
        self._participants: set[str] = set()

    def register_participant(self, tenant_id: str) -> dict:
        """企业注册参与产业链联邦。"""
        self._participants.add(tenant_id)
        logger.info(f"🏭 产业链联邦参与者注册: {tenant_id}")
        return {"tenant_id": tenant_id, "status": "active", "participants": len(self._participants)}

    # ---------------- 目标共享 ----------------

    def share_goal(
        self,
        origin_tenant: str,
        goal: str,
        target_products: list[str] | None = None,
        target_materials: list[str] | None = None,
        urgency: str = "normal",
        deadline: str = "",
    ) -> dict:
        """共享一个供应链目标到产业链联邦（去标识化）。

        比如 "保持某客户订单交付" 可以被上游供应商的 Agent 看到并协同。
        但不会暴露企业名称、价格、合同条款。
        """
        goal_id = f"fsg-{uuid.uuid4().hex[:8]}"
        rec = {
            "id": goal_id,
            "origin": self._anonymize_tenant(origin_tenant),
            "goal": goal,
            "target_products": target_products or [],
            "target_materials": target_materials or [],
            "urgency": urgency,
            "deadline": deadline,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "participating": [origin_tenant],
        }
        self._shared_goals.append(rec)
        logger.info(f"🎯 产业链目标共享: {goal_id} — {goal[:60]}")
        return rec

    def join_goal(self, goal_id: str, tenant_id: str) -> dict | None:
        """某企业加入一个共享目标。"""
        for g in self._shared_goals:
            if g["id"] == goal_id and g["status"] == "active":
                if tenant_id not in g["participating"]:
                    g["participating"].append(tenant_id)
                return g
        return None

    def list_active_goals(self, tenant_id: str | None = None) -> list[dict]:
        """列出活跃的产业链目标（按参与度排序）。"""
        out = [
            {
                "id": g["id"],
                "origin": g["origin"],
                "goal": g["goal"],
                "target_products": g["target_products"],
                "target_materials": g["target_materials"],
                "urgency": g["urgency"],
                "deadline": g["deadline"],
                "participant_count": len(g["participating"]),
                "is_participating": tenant_id in g["participating"] if tenant_id else False,
            }
            for g in self._shared_goals
            if g["status"] == "active"
        ]
        return sorted(out, key=lambda x: -x["participant_count"])

    # ---------------- 跨企业风险聚合 ----------------

    def report_risk(
        self, tenant_id: str, material: str, risk_level: str, description: str
    ) -> dict:
        """企业报告一个供应链风险到联邦（去标识化）。

        如 "某进口光刻胶可能延期" → 下游企业自动获知风险但不暴露供应商名。
        """
        rid = f"fsr-{uuid.uuid4().hex[:8]}"
        rec = {
            "id": rid,
            "reporter": self._anonymize_tenant(tenant_id),
            "material": self._anonymize_material(material),
            "material_type": self._infer_material_type(material),
            "risk_level": risk_level,
            "description": description[:200],
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cross_risks.append(rec)
        logger.info(f"⚠️ 供应链风险报告: {rid} — {risk_level} {material}")
        return rec

    def resolve_risk(self, risk_id: str) -> dict | None:
        """标记风险已解决。"""
        for r in self._cross_risks:
            if r["id"] == risk_id:
                r["status"] = "resolved"
                return r
        return None

    def aggregate_risks(self) -> dict:
        """聚合跨企业风险视图（匿名化）。"""
        active = [r for r in self._cross_risks if r["status"] == "active"]

        by_level = defaultdict(int)
        by_type = defaultdict(int)
        for r in active:
            by_level[r["risk_level"]] += 1
            by_type[r["material_type"]] += 1

        return {
            "summary": {
                "total_active_risks": len(active),
                "total_resolved": sum(1 for r in self._cross_risks if r["status"] == "resolved"),
                "risk_levels": dict(by_level),
                "material_types": dict(by_type),
            },
            "recent_risks": [
                {
                    "id": r["id"],
                    "material": r["material"],
                    "material_type": r["material_type"],
                    "risk_level": r["risk_level"],
                    "description": r["description"],
                    "reporter": r["reporter"],
                    "created_at": r["created_at"],
                    "status": r["status"],
                }
                for r in active[-10:]
            ],
        }

    # ---------------- 联合计划 ----------------

    def create_joint_plan(
        self, initiator: str, goal_id: str, plan: str
    ) -> dict:
        """基于共享目标创建联合执行计划。"""
        pid = f"fjp-{uuid.uuid4().hex[:8]}"
        rec = {
            "id": pid,
            "initiator": self._anonymize_tenant(initiator),
            "goal_id": goal_id,
            "plan": plan,
            "status": "proposed",
            "participants": [initiator],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._joint_plans.append(rec)
        logger.info(f"📋 联合计划创建: {pid} — 目标 {goal_id}")
        return rec

    def join_plan(self, plan_id: str, tenant_id: str) -> dict | None:
        """企业加入一个联合计划。"""
        for p in self._joint_plans:
            if p["id"] == plan_id and p["status"] == "proposed":
                if tenant_id not in p["participants"]:
                    p["participants"].append(tenant_id)
                return p
        return None

    def approve_plan(self, plan_id: str) -> dict | None:
        """批准联合计划（所有参与方同意后进入执行状态）。"""
        for p in self._joint_plans:
            if p["id"] == plan_id:
                p["status"] = "active"
                return p
        return None

    def list_plans(self, status: str | None = None) -> list[dict]:
        """列出联合计划。"""
        out = self._joint_plans
        if status:
            out = [p for p in out if p["status"] == status]
        return sorted(out, key=lambda x: x["created_at"], reverse=True)

    # ---------------- 联邦状态 ----------------

    def federation_status(self) -> dict:
        """产业链联邦整体状态。"""
        return {
            "participants": {
                "count": len(self._participants),
                "anonymized": [self._anonymize_tenant(t) for t in self._participants],
            },
            "goals": {
                "active": len([g for g in self._shared_goals if g["status"] == "active"]),
                "total": len(self._shared_goals),
            },
            "risks": self.aggregate_risks()["summary"],
            "plans": {
                "active": len([p for p in self._joint_plans if p["status"] == "active"]),
                "proposed": len([p for p in self._joint_plans if p["status"] == "proposed"]),
                "total": len(self._joint_plans),
            },
        }

    @staticmethod
    def _anonymize_tenant(tenant_id: str) -> str:
        """租户 ID 去标识化。"""
        if len(tenant_id) >= 6:
            return f"企业{tenant_id[:3].upper()}**"
        return f"企业{tenant_id[:2]}**"

    @staticmethod
    def _anonymize_material(material: str) -> str:
        if len(material) >= 4:
            return material[:2] + "***" + material[-1]
        return material + "***"

    @staticmethod
    def _infer_material_type(material: str) -> str:
        m = material.lower()
        if any(x in m for x in ("硅片", "wafer", "硅")):
            return "wafer"
        if any(x in m for x in ("光刻胶", "resist", "pr")):
            return "photoresist"
        if any(x in m for x in ("靶材", "target")):
            return "target_material"
        if any(x in m for x in ("电子", "电容", "电阻", "ic", "chip")):
            return "electronic"
        if any(x in m for x in ("特气", "gas", "nf3")):
            return "special_gas"
        return "general_material"


# 全局单例
federated_supply_chain = FederatedSupplyChain()
