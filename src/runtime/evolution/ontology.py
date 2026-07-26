"""v25.0 工业本体自生长（Ontology Self-Growth）

从 KG 事实提议中自动发现新实体类型和关系类型 → 提议本体扩展 → 审批门批准。

关键设计：
- 从实体前缀自动发现实体类型（EMP: → Employee, SUP: → Supplier, MAT: → Material 等）
- 从 KG 事实 predicate 自动发现关系类型
- 提议→审批门：新本体元素须经人工 approve 才纳入 schema
- 不修改现有 KG 节点标签，仅管控 schema 定义
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.runtime.evolution.kg_facts import kg_facts

logger = logging.getLogger(__name__)


# ---- 已知实体类型前缀映射（作为种子本体）----
KNOWN_ENTITY_PREFIXES: dict[str, str] = {
    "EMP:": "Employee",
    "SUP:": "Supplier",
    "MAT:": "Material",
    "DEV:": "Device",
    "LINE:": "ProductionLine",
    "INSIGHT:": "Insight",
    "ENTITY:": "Entity",
    "ORDER:": "Order",
    "CUST:": "Customer",
    "PROD:": "Product",
    "MACH:": "Machine",
    "SENSOR:": "Sensor",
    "BATCH:": "Batch",
    "QUAL:": "QualityCheck",
    "COST:": "CostCenter",
    "ENERGY:": "EnergyMeter",
}

# ---- 已知关系预测类型（种子本体）----
KNOWN_PREDICATES: dict[str, str] = {
    "tacit_judges": "人类隐性判断",
    "observed_in": "被观察到存在于",
    "decided": "决策结果为",
    "collaborated_on": "协作处理",
    "signals": "发出信号",
    "supplies": "供应",
    "manufactures": "制造",
    "monitors": "监控",
    "reports_to": "汇报给",
    "maintains": "维护",
}


def infer_entity_type(entity_str: str) -> str:
    """从实体字符串推断实体类型（基于已知前缀或默认 Entity）。"""
    for prefix, etype in KNOWN_ENTITY_PREFIXES.items():
        if entity_str.startswith(prefix):
            return etype
    return "Entity"


def _entity_type_from_subject(subject: str) -> str:
    return infer_entity_type(subject)


def _entity_type_from_object(object_val: str) -> str:
    return infer_entity_type(object_val)


@dataclass
class SchemaElement:
    """一个本体 schema 元素（实体类型或关系类型）。"""
    id: str
    kind: str  # "entity_type" | "relationship_type"
    name: str
    description: str = ""
    status: str = "active"  # active | proposed | deprecated
    source: str = "seed"  # seed | discovered | manual
    created_at: str = ""
    proposals: list[dict] = field(default_factory=list)


class OntologyStore:
    """工业本体 schema 管理 + 自生长。"""

    def __init__(self):
        # 已注册 schema 元素（id → SchemaElement）
        self._elements: dict[str, SchemaElement] = {}
        # 待审批的扩展提议
        self._extension_proposals: list[dict] = []
        # 初始化种子本体
        self._init_seed()

    def _init_seed(self) -> None:
        for prefix, name in KNOWN_ENTITY_PREFIXES.items():
            self._add_seed(f"et:{name}", "entity_type", name, f"实体类型：{prefix}前缀实体")
        for pred, desc in KNOWN_PREDICATES.items():
            self._add_seed(f"rt:{pred}", "relationship_type", pred, desc)

    def _add_seed(self, eid: str, kind: str, name: str, desc: str) -> None:
        if eid not in self._elements:
            self._elements[eid] = SchemaElement(
                id=eid, kind=kind, name=name, description=desc,
                status="active", source="seed",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

    # ---------------- Schema 查询 ----------------

    def entity_types(self) -> list[SchemaElement]:
        return [e for e in self._elements.values() if e.kind == "entity_type" and e.status == "active"]

    def relationship_types(self) -> list[SchemaElement]:
        return [e for e in self._elements.values() if e.kind == "relationship_type" and e.status == "active"]

    def schema_summary(self) -> dict:
        return {
            "total_elements": len(self._elements),
            "entity_types": len(self.entity_types()),
            "relationship_types": len(self.relationship_types()),
            "pending_proposals": len(self._extension_proposals),
            "active_elements": sum(1 for e in self._elements.values() if e.status == "active"),
            "proposed_elements": sum(1 for e in self._elements.values() if e.status == "proposed"),
        }

    def list_elements(self, status: str | None = None) -> list[dict]:
        out = []
        for e in self._elements.values():
            if status and e.status != status:
                continue
            out.append({
                "id": e.id,
                "kind": e.kind,
                "name": e.name,
                "description": e.description,
                "status": e.status,
                "source": e.source,
                "created_at": e.created_at,
            })
        return out

    # ---------------- 模式发现（自生长核心） ----------------

    def discover(self) -> dict:
        """扫描全部 KG 事实提议，发现潜在的新实体类型和关系类型。

        返回结构：
        {
            "candidate_entity_types": [str],   # 未注册的实体类型候选
            "candidate_relationship_types": [str],  # 未注册的关系类型候选
            "entity_type_evidence": {etype: count},  # 出现频次证据
            "relationship_evidence": {predicate: count},
            "total_proposals_scanned": int,
        }
        """
        proposals = kg_facts.list_proposals()
        # 不传 agent 筛选，获取所有提议

        entity_evidence: dict[str, int] = defaultdict(int)
        pred_evidence: dict[str, int] = defaultdict(int)

        for p in proposals:
            subj = p.get("subject", "")
            obj_val = p.get("object_val", "")
            predicate = p.get("predicate", "")

            # 提取 subject 的实体类型
            etype = infer_entity_type(subj)
            if not self._has_entity_type(etype):
                entity_evidence[etype] += 1

            # 提取 object 的实体类型
            otype = infer_entity_type(obj_val)
            if not self._has_entity_type(otype):
                entity_evidence[otype] += 1

            # 关系类型
            if not self._has_relationship_type(predicate):
                pred_evidence[predicate] += 1

        # 生成候选列表（出现频次 ≥ 2 才算有证据）
        candidate_entity_types = [
            {"name": etype, "count": cnt}
            for etype, cnt in entity_evidence.items()
            if cnt >= 2 and etype != "Entity"
        ]
        candidate_relationship_types = [
            {"name": pred, "count": cnt}
            for pred, cnt in pred_evidence.items()
            if cnt >= 2
        ]

        return {
            "summary": {
                "total_proposals_scanned": len(proposals),
                "candidate_entity_types": len(candidate_entity_types),
                "candidate_relationship_types": len(candidate_relationship_types),
            },
            "candidate_entity_types": sorted(candidate_entity_types, key=lambda x: -x["count"]),
            "candidate_relationship_types": sorted(candidate_relationship_types, key=lambda x: -x["count"]),
        }

    def _has_entity_type(self, name: str) -> bool:
        return any(e.name == name and e.status == "active" for e in self._elements.values() if e.kind == "entity_type")

    def _has_relationship_type(self, name: str) -> bool:
        return any(e.name == name and e.status == "active" for e in self._elements.values() if e.kind == "relationship_type")

    # ---------------- 扩展提议 ----------------

    def propose_extension(self, kind: str, name: str, description: str = "") -> dict:
        """提议一条本体扩展（实体类型或关系类型）。

        返回提议 dict，status="proposed"，待人工审批。
        """
        existing = any(
            e.name == name and e.kind == kind
            for e in self._elements.values()
        )
        if existing:
            raise ValueError(f"本体元素已存在：{kind}/{name}")

        proposal = {
            "id": f"onto-{uuid.uuid4().hex[:12]}",
            "kind": kind,
            "name": name,
            "description": description,
            "status": "proposed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._extension_proposals.append(proposal)

        # 同时加入 _elements 等待审批
        eid = f"{'et' if kind == 'entity_type' else 'rt'}:{name}"
        self._elements[eid] = SchemaElement(
            id=eid, kind=kind, name=name, description=description,
            status="proposed", source="discovered",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(f"🧬 本体扩展已提议：{kind}「{name}」— {description}")
        return proposal

    def approve_extension(self, proposal_id: str) -> dict:
        """人工审批通过一条本体扩展提议。"""
        proposal = None
        for p in self._extension_proposals:
            if p["id"] == proposal_id:
                proposal = p
                break
        if not proposal:
            raise KeyError(f"本体扩展提议不存在：{proposal_id}")

        proposal["status"] = "approved"
        eid = f"{'et' if proposal['kind'] == 'entity_type' else 'rt'}:{proposal['name']}"
        if eid in self._elements:
            self._elements[eid].status = "active"
            self._elements[eid].source = "discovered"

        logger.info(f"🧬 本体扩展已批准：{proposal['kind']}「{proposal['name']}」")
        return proposal

    def list_proposals(self) -> list[dict]:
        return list(self._extension_proposals)


# 全局单例
ontology = OntologyStore()
