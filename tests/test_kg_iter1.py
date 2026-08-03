"""刀1 知识图谱升级 · 迭代1 测试（2026-08-03）

覆盖：
- build_from_cases 从现有研究案例抽取最小实体-关系图
  - 实体：行业 / 产业节点 / 企业锚（匿名）
  - 关系：VALUE_CHAIN（行业↔节点↔企业锚归属）、COMPETES_WITH（同节点对标）
- 企业锚节点数 == len(DEFAULT_CASES)（不扩数据，只读）
- 半导体行业（10 锚 / 5 价值链节点）生成 COMPETES_WITH 对标边
- 🔴 匿名铁律：图谱 to_dict 不含任何 LEAK_TOKENS 真实锚定片段

范围纪律（docs/TECHNICAL_DELIVERY_SCOPE.md）：本测试只验证迭代1 最小抽取，
不涉存储 / UI / 跨行业扩展。
"""
import json

from src.agents.case_curator.agent import DEFAULT_CASES
from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.knowledge_graph.builder import build_from_cases
from src.knowledge_graph.taxonomy import SPINE_LEVELS, RELATION_TYPES


def test_kg_taxonomy_constants():
    assert len(SPINE_LEVELS) == 5, "脊应为 5 级（行业/产业节点/企业/岗位/对象）"
    assert "COMPETES_WITH" in RELATION_TYPES
    assert "VALUE_CHAIN" in RELATION_TYPES


def test_kg_build_basic():
    g = build_from_cases(DEFAULT_CASES)
    assert g.node_count() > 0
    assert g.node_count("industry") >= 1
    assert g.node_count("enterprise") == len(DEFAULT_CASES), \
        "企业锚节点数须等于案例数（只读，不扩数据）"
    assert g.edge_count("VALUE_CHAIN") >= g.node_count("enterprise"), \
        "每个企业锚至少有一条归属边"
    # 半导体 10 锚分布在 5 个价值链节点，每组 2 锚 -> 每组 1 条对标边 = 5 条
    comp_edges = [e for e in g.edges if e.relation == "COMPETES_WITH"]
    semicon_comp = [
        e for e in comp_edges
        if any(n.id == e.source and n.props.get("industry_key") == "semiconductor"
               for n in g.nodes)
        and any(n.id == e.target and n.props.get("industry_key") == "semiconductor"
                for n in g.nodes)
    ]
    assert len(semicon_comp) >= 5, f"半导体对标边应≥5，实际 {len(semicon_comp)}"


def test_kg_zero_real_name_leak():
    """图谱对外序列化不得含任何真实锚定片段。"""
    g = build_from_cases(DEFAULT_CASES)
    blob = json.dumps(g.to_dict(), ensure_ascii=False)
    hits = [t for t in LEAK_TOKENS if t in blob]
    assert not hits, f"❌ 知识图谱泄露真实锚定名：{hits}"


def test_kg_no_new_industry_introduced():
    """迭代1 不得引入案例外的新行业（范围护栏）。"""
    g = build_from_cases(DEFAULT_CASES)
    ikeys = {n.props.get("industry_key") for n in g.nodes
             if n.level == "industry" and n.props.get("industry_key")}
    allowed = {"telecom", "semiconductor", "consumer_electronics", "new_energy"}
    assert ikeys <= allowed, f"❌ 引入未授权行业：{ikeys - allowed}"
