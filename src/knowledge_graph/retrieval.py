"""知识图谱检索 + 绑定钩子（刀1 迭代3）。

提供：
- ``get_graph()`` 懒加载工厂：从现有研究案例（DEFAULT_CASES）构建一次、缓存复用，
  供运行时（孪生 / 记忆 / 技能）按需查询，不触发外部 API、不重复抽取。
- 绑定钩子骨架：声明图谱与「孪生 / 记忆 / 技能」三类资产的挂载点（钩子接口），
  供后续迭代接入；本迭代只落地接口与最小索引，不实现重迁移。

设计纪律（范围基线 docs/TECHNICAL_DELIVERY_SCOPE.md §3/§6）：
- 零真名：对外查询返回节点只含 case_id / industry_key / scope / node_category 等匿名字段。
- 不扩数据：只读 DEFAULT_CASES，不新增案例 / 行业 / agent。
- 延迟部署：纯后端结构化，未接入运行时 import，符合基线 §4。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.agents.case_curator.agent import DEFAULT_CASES
from src.knowledge_graph.builder import KGGraph, build_from_cases

# 进程级缓存：图谱构建一次复用
_graph_cache: Optional[KGGraph] = None


def get_graph() -> KGGraph:
    """懒加载知识图谱（从现有案例构建一次，缓存复用）。"""
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = build_from_cases(DEFAULT_CASES)
    return _graph_cache


def get_enterprises_by_node(industry_key: str, node_category: str) -> List[dict]:
    """按 (行业, 价值链节点类别) 检索对标企业锚（对外匿名视图）。"""
    g = get_graph()
    nodes = g.enterprises_by_node(industry_key, node_category)
    return _anon_view(nodes)


def get_competitors(enterprise_id: str) -> List[dict]:
    """检索给定企业锚的同节点对标企业（匿名视图）。"""
    g = get_graph()
    return _anon_view(g.competitors_of(enterprise_id))


def get_upstream(enterprise_id: str) -> List[dict]:
    """检索上游供应商（匿名视图）。"""
    g = get_graph()
    return _anon_view(g.upstream_of(enterprise_id))


def get_downstream(enterprise_id: str) -> List[dict]:
    """检索下游客户（匿名视图）。"""
    g = get_graph()
    return _anon_view(g.downstream_of(enterprise_id))


def _anon_view(nodes: List) -> List[dict]:
    """导出对外匿名视图：只留非真名字段。"""
    out = []
    for n in nodes:
        out.append({
            "enterprise_id": n.id,
            "industry_key": n.props.get("industry_key"),
            "scope": n.props.get("scope"),
            "node_category": n.props.get("node_category"),
            "label": n.label,  # 已是 subject_anon 匿名标签
        })
    return out


# ---------------------------------------------------------------------------
# 绑定钩子骨架（刀1 迭代3 · DoD：与孪生 / 记忆 / 技能 绑定钩子）
# ---------------------------------------------------------------------------
# 三类资产挂载点：图谱作为「认知层资产」的索引，可被孪生状态、记忆、技能反向关联。
# 本迭代落地接口与最小索引（不实现重迁移，符合基线 §3 不引图库重型设施）。
BINDING_HOOKS: Dict[str, str] = {
    "twin": "twin_state.node_bindings",        # 孪生对象 → 图谱节点（行业/产业节点/对象）
    "memory": "enterprise_memory.case_bindings",  # 企业级记忆 → 企业锚
    "skill": "preset_library.node_bindings",   # 预设技能库 → 价值链节点类别
}


def resolve_binding_target(asset_kind: str) -> Optional[str]:
    """返回某类资产在图谱上的绑定挂载点（钩子接口，供后续迭代接入实现）。"""
    return BINDING_HOOKS.get(asset_kind)
