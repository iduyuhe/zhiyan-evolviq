"""知识图谱最小抽取（刀1 迭代1）。

输入：研究案例列表（DEFAULT_CASES / cases.json 的反序列化）。
输出：KGGraph（nodes + edges），可供后续迭代做检索 / 绑定孪生。

设计纪律（范围基线 docs/TECHNICAL_DELIVERY_SCOPE.md §3/§6）：
- 零真名：只用 case_id / industry_key / scope / value_chain_node / subject_anon。
- 不扩数据：只读现有案例，不新增案例、不新增行业、不改案例字段。
- 单文件改动：本文件 + taxonomy.py + 测试，不碰其他模块。

⚠️ 关于 value_chain_node 归一化：现有案例的 value_chain_node 是带括号描述的
自由文本（如台积电="制造（先进制程产能咽喉）"、中芯="晶圆代工（国内制程追赶主轴）"），
同价值链节点类别（代工/设备/设计/存储/封测）的国内外锚描述不同。为支持
「同节点国际↔国内对照」语义，本模块在 builder 内做**类别归一化**（不写回数据），
提取括号前类别词并同义归并（制造/晶圆代工→代工、存储与 IDM→存储）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from src.knowledge_graph.taxonomy import SPINE_LEVELS, RELATION_TYPES

# 价值链节点类别同义归并（仅 builder 内映射，不污染数据）
_NODE_CATEGORY_ALIAS = {
    "制造": "代工",
    "晶圆代工": "代工",
    "存储与 IDM": "存储",
    "存储与IDM": "存储",
    "封装测试": "封测",
}


def _slug(s: str | None) -> str:
    if not s:
        return "x"
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s).strip("_")[:40] or "x"


def _normalize_node_category(vcn: str | None) -> str | None:
    """从自由文本 value_chain_node 提取价值链节点类别（归一化）。

    例：'制造（先进制程产能咽喉）' -> '代工'；'设备（国产替代主轴）' -> '设备'。
    """
    if not vcn:
        return None
    cat = re.split(r"[（(]", vcn)[0].strip()
    return _NODE_CATEGORY_ALIAS.get(cat, cat)


@dataclass
class KGNode:
    id: str
    level: str          # SPINE_LEVELS 之一
    kind: str           # ENTITY_TYPES 之一
    label: str          # 对外展示名（匿名）
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KGEdge:
    source: str
    target: str
    relation: str       # RELATION_TYPES 之一
    props: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KGGraph:
    nodes: List[KGNode]
    edges: List[KGEdge]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }

    def node_count(self, level: str | None = None) -> int:
        if level is None:
            return len(self.nodes)
        return sum(1 for n in self.nodes if n.level == level)

    def edge_count(self, relation: str | None = None) -> int:
        if relation is None:
            return len(self.edges)
        return sum(1 for e in self.edges if e.relation == relation)


def build_from_cases(cases: List[Dict[str, Any]]) -> KGGraph:
    """从研究案例抽取最小知识图谱。

    实体：行业 / 产业节点（价值链节点类别）/ 企业锚（匿名）。
    关系：
      - VALUE_CHAIN：行业→产业节点（包含）、父节点→企业锚（归属/对标载体）。
      - COMPETES_WITH：同产业节点类别内的企业锚两两（国际↔国内对照）。
    """
    nodes: List[KGNode] = []
    edges: List[KGEdge] = []
    seen: set[str] = set()

    industry_node_ids: Dict[str, str] = {}          # (industry_key, cat) -> node_id
    enterprises_by_node: Dict[str, List[str]] = {}  # (industry_key, cat) -> [ent_id...]

    for c in cases:
        ik = c.get("industry_key")
        if not ik:
            continue  # 范围纪律：无 industry_key 的案例不参与图谱（应按基线补全）
        vcn = c.get("value_chain_node")
        cat = _normalize_node_category(vcn)  # 归一化类别（代工/设备/设计/存储/封测）
        scope = c.get("scope", "domestic")
        cid = c["case_id"]
        label = c.get("subject_anon") or cid  # 🔴 匿名标签，零真名

        # 1) 行业节点（每个 industry_key 唯一）
        ind_id = f"industry:{ik}"
        if ind_id not in seen:
            seen.add(ind_id)
            nodes.append(KGNode(ind_id, "industry", "industry", ik, {"industry_key": ik}))

        # 2) 产业节点（有 cat 才建；否则企业锚直接挂行业节点）
        if cat:
            inn_key = f"{ik}|{cat}"
            inn_id = f"industry_node:{ik}:{cat}"
            if inn_id not in seen:
                seen.add(inn_id)
                nodes.append(KGNode(
                    inn_id, "industry_node", "industry_node", cat,
                    {"industry_key": ik, "node_category": cat,
                     "value_chain_node_raw": vcn},
                ))
                edges.append(KGEdge(ind_id, inn_id, "VALUE_CHAIN",
                                    {"note": "行业包含该价值链节点"}))
            parent_id = inn_id
        else:
            parent_id = ind_id
            inn_key = f"{ik}|"

        # 3) 企业锚节点（匿名）
        ent_id = f"enterprise:{cid}"
        nodes.append(KGNode(
            ent_id, "enterprise", "enterprise", label,
            {"case_id": cid, "scope": scope, "industry_key": ik,
             "node_category": cat, "value_chain_node": vcn},
        ))
        edges.append(KGEdge(parent_id, ent_id, "VALUE_CHAIN",
                            {"role": "anchor_of_node", "scope": scope}))

        enterprises_by_node.setdefault(inn_key, []).append(ent_id)

    # 4) COMPETES_WITH：同产业节点类别内的企业锚两两（国际↔国内对照）
    for ent_ids in enterprises_by_node.values():
        for i in range(len(ent_ids)):
            for j in range(i + 1, len(ent_ids)):
                edges.append(KGEdge(
                    ent_ids[i], ent_ids[j], "COMPETES_WITH",
                    {"basis": "同价值链节点对标"},
                ))

    return KGGraph(nodes, edges)
