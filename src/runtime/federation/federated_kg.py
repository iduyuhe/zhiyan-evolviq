"""v24.0 联邦知识图谱 —— 跨租户 KG 事实模式匿名聚合

从所有活跃租户的 KG 事实提议中提取去标识化的结构模式，
追踪同模式在不同租户间的验证情况，生成「联邦可信」事实候选。

关键设计：
- 去标识化：只保留 (predicate, object_type, confidence_range) 三元组，不保留具体实体值
- 跨租户同模式：同一 predicate+object_type 模式被多个租户独立 validate 则提升联邦可信度
- 绝不泄露任何租户的具体业务数据
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from src.runtime.evolution.kg_facts import kg_facts

logger = logging.getLogger(__name__)


def _object_type(val: str) -> str:
    """从 KG 事实的 object_val 推断类型（去标识化）。"""
    val = val.strip()
    if not val:
        return "unknown"
    if val.startswith("EMP:") or val.startswith("SUP:") or val.startswith("DEV:"):
        return "entity"
    if val.startswith("LINE:") or val.startswith("MAT:"):
        return "entity"
    if val.startswith("INSIGHT:"):
        return "insight"
    if val.startswith("ENTIT"):
        return "entity"
    # 数值型
    try:
        float(val)
        return "numeric"
    except ValueError:
        pass
    # 短文本
    if len(val) <= 20:
        return "short_label"
    return "description"


class FederatedKG:
    """跨租户 KG 事实模式聚合器。"""

    def __init__(self):
        # 聚合结果缓存（惰性刷新）
        self._cache: dict | None = None
        self._cache_ts: float = 0
        self._cache_ttl = 30  # 秒

    def _invalidate(self) -> None:
        self._cache = None

    def aggregate(self, force: bool = False) -> dict:
        """从所有租户的 KG 事实提议中聚合去标识化的结构模式。

        返回：
            patterns: dict[predicate][object_type] = {
                tenant_count: 有多少租户提出过该模式
                total_count: 总提议次数
                validated_count: 被 validate 的总次数
                contradicted_count: 被矛盾的总次数
                federal_trust: 联邦可信度 (0-1)
                sample_tenant_ids: 示例租户 ID 列表（最多 3 个，仅用于调试）
            }
        """
        if self._cache and not force:
            return self._cache

        # 收集所有租户的事实提议
        proposals = kg_facts.list_proposals()

        # 按 (predicate, object_type, tenant) 聚合
        pattern_tenants: dict[tuple[str, str], set[str]] = defaultdict(set)
        pattern_stats: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"total": 0, "validated": 0, "needs_review": 0, "draft": 0}
        )

        for p in proposals:
            predicate = p.get("predicate", "?")
            obj_type = _object_type(p.get("object_val", ""))
            tenant = p.get("tenant_id", "default")
            status = p.get("status", "draft")

            key = (predicate, obj_type)
            pattern_tenants[key].add(tenant)
            pat = pattern_stats[key]
            pat["total"] += 1
            if status == "validated":
                pat["validated"] += 1
            elif status == "needs_review":
                pat["needs_review"] += 1
            elif status == "draft":
                pat["draft"] += 1

        # 生成聚合结果
        result: dict[str, dict[str, Any]] = {}
        for (predicate, obj_type), tenants in pattern_tenants.items():
            stats = pattern_stats[(predicate, obj_type)]
            tenant_count = len(tenants)
            validated = stats["validated"]
            total = stats["total"]
            # 联邦可信度：被多个租户独立 validate 的模式具有更高可信度
            federal_trust = min(1.0, (validated / max(total, 1)) * 0.7 + (tenant_count / max(len(kg_facts.list_proposals()), 1)) * 0.3)
            # 展示用 tenant 样本（取前 3，去标识化不暴露名称）
            sample_ids = sorted(tenants)[:3]

            if predicate not in result:
                result[predicate] = {}
            result[predicate][obj_type] = {
                "tenant_count": tenant_count,
                "total_count": total,
                "validated_count": validated,
                "contradicted_count": stats["needs_review"],
                "draft_count": stats["draft"],
                "federal_trust": round(federal_trust, 3),
                "sample_tenants": sample_ids,
            }

        # 全聚合摘要
        total_patterns = sum(len(obj_map) for obj_map in result.values())
        multi_tenant_patterns = sum(
            1 for obj_map in result.values() for v in obj_map.values() if v["tenant_count"] > 1
        )

        self._cache = {
            "summary": {
                "total_patterns": total_patterns,
                "multi_tenant_patterns": multi_tenant_patterns,
                "federated_tenants": len(set(
                    p.get("tenant_id", "default") for p in proposals
                )),
            },
            "patterns": result,
        }
        self._cache_ts = datetime.now(timezone.utc).timestamp()
        return self._cache

    def high_trust_patterns(self, min_trust: float = 0.6) -> list[dict]:
        """返回高于指定联邦可信度的模式（可用于跨租户建议）。"""
        data = self.aggregate()
        results = []
        for predicate, obj_types in data.get("patterns", {}).items():
            for obj_type, stats in obj_types.items():
                if stats["federal_trust"] >= min_trust and stats["tenant_count"] > 1:
                    results.append({
                        "predicate": predicate,
                        "object_type": obj_type,
                        "federal_trust": stats["federal_trust"],
                        "tenant_count": stats["tenant_count"],
                        "validated_count": stats["validated_count"],
                    })
        return sorted(results, key=lambda x: x["federal_trust"], reverse=True)


# 全局单例
federated_kg = FederatedKG()
