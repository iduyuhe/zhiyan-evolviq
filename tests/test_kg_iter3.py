"""刀1 知识图谱升级 · 迭代3 测试（检索接口 + 懒加载 + 绑定钩子）

覆盖：
- get_graph() 懒加载 + 进程级缓存（构建一次复用）
- KGGraph 检索方法：enterprises_by_node / competitors_of / upstream_of / downstream_of
- 对外匿名视图（零真名）
- 绑定钩子 resolve_binding_target（孪生/记忆/技能挂载点）

范围纪律（docs/TECHNICAL_DELIVERY_SCOPE.md）：仅后端结构化，不扩行业/案例/agent，
不接入运行时 import，符合延迟部署纪律。
"""
from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.knowledge_graph.builder import build_from_cases
from src.knowledge_graph.retrieval import (
    get_graph,
    get_enterprises_by_node,
    get_competitors,
    get_upstream,
    get_downstream,
    resolve_binding_target,
)
from src.agents.case_curator.agent import DEFAULT_CASES


def _ent_id(case_id: str) -> str:
    return f"enterprise:{case_id}"


def test_get_graph_cached():
    g1 = get_graph()
    g2 = get_graph()
    assert hasattr(g1, "nodes") and hasattr(g1, "edges")
    assert g1 is g2, "get_graph() 应缓存复用同一图谱实例"


def test_enterprises_by_node():
    g = get_graph()
    foundry = g.enterprises_by_node("semiconductor", "代工")
    assert len(foundry) == 2, f"半导体代工节点应 2 锚，实际 {len(foundry)}"
    ids = {n.id for n in foundry}
    assert _ent_id("case_semicon_2026") in ids
    assert _ent_id("case_semicon_foundry_global_2026") in ids


def test_competitors_of():
    g = get_graph()
    comp = g.competitors_of(_ent_id("case_semicon_2026"))
    comp_ids = {n.id for n in comp}
    assert _ent_id("case_semicon_foundry_global_2026") in comp_ids, \
        "国内代工锚应与全球代工龙头对标"


def test_upstream_downstream():
    g = get_graph()
    # 封测锚的上游 = 代工(2) + 设备(2) + 存储(1)
    osat = _ent_id("case_semicon_osat_cn_2026")
    up = g.upstream_of(osat)
    up_cats = {n.props.get("node_category") for n in up}
    assert up_cats == {"代工", "设备", "存储"}, f"封测上游应含代工/设备/存储，实际 {up_cats}"
    assert g.downstream_of(osat) == [], "封测无下游"
    # 代工锚的下游 = 封测(2)，上游 = 设备 + 设计
    foundry = _ent_id("case_semicon_2026")
    down = g.downstream_of(foundry)
    assert {n.props.get("node_category") for n in down} == {"封测"}
    up_cats_f = {n.props.get("node_category") for n in g.upstream_of(foundry)}
    assert up_cats_f == {"设备", "设计"}, f"代工上游应含设备/设计，实际 {up_cats_f}"


def test_retrieval_anon_view_zero_leak():
    """对外匿名视图不得含真实锚定片段。"""
    view = get_enterprises_by_node("semiconductor", "代工")
    blob = str(view)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 检索视图泄露真实锚定名：{hits}"
    # 视图只含匿名字段
    allowed_keys = {"enterprise_id", "industry_key", "scope", "node_category", "label"}
    for row in view:
        assert set(row.keys()) <= allowed_keys


def test_binding_hooks():
    """绑定钩子：孪生/记忆/技能三类资产挂载点可解析。"""
    assert resolve_binding_target("twin") == "twin_state.node_bindings"
    assert resolve_binding_target("memory") == "enterprise_memory.case_bindings"
    assert resolve_binding_target("skill") == "preset_library.node_bindings"
    assert resolve_binding_target("unknown") is None


def test_build_from_cases_still_works():
    """回归：builder 底层抽取未被检索接口破坏。"""
    g = build_from_cases(DEFAULT_CASES)
    assert g.node_count("enterprise") == len(DEFAULT_CASES)
    assert g.edge_count("SUPPLIES") > 0
