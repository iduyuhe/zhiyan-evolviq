"""P2 研究案例扩列 + 设备预设扩列测试（2026-07-31）

覆盖：
- P2-A 研究案例：案例库从 2 行业扩至 4 行业（通讯+半导体+3C+新能源）
  - DEFAULT_CASES 含 case_3c_2026 / case_newenergy_2026
  - ANON_SCRUB_MAP 含立讯精密/002475/宁德时代/300750 擦洗项
  - 对外视图（详情/列表/教学）零真名泄漏
- P2-B 设备预设：设备库从半导体 6 类扩至 3 行业 12 类
  - EQUIPMENT_CATEGORIES 含 3C(SMT/CNC/注塑) + 新能源(涂布/卷绕/化成分容)
  - PROFILES 含 smt_1/cnc_1/injection_1/coating_1/winding_1/formation_1
  - presets.get_preset_summary() equipment_types 覆盖新行业设备类型

🔴 匿名铁律：LEAK_TOKENS 对一切外发结果断言零真名。
"""

import json

import pytest

from src.agents.case_curator.agent import (
    ANON_SCRUB_MAP,
    DEFAULT_CASES,
    case_curator_agent,
)
from src.agents.pm_maintenance import equipment_profiles
from src.presets import get_preset_summary

# 所有真实锚定片段（含历史 + 新增），外发结果一律不得出现
LEAK_TOKENS = [
    "中兴", "000063", "ZTE", "zte",
    "中芯", "688981", "00981", "SMIC", "smic",
    "立讯", "002475", "Luxshare", "luxshare",
    "宁德", "300750", "CATL", "catl",
]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


def test_p2a_case_count_four_industries():
    ids = {c["case_id"] for c in DEFAULT_CASES}
    assert "case_telecom_2026" in ids
    assert "case_semicon_2026" in ids
    assert "case_3c_2026" in ids
    assert "case_newenergy_2026" in ids
    # 2026-08-03 杜总定调：第一批全球化锚（晶圆代工 + 光刻设备）
    assert "case_semicon_foundry_global_2026" in ids
    assert "case_semicon_litho_global_2026" in ids
    # 🔴 范围纪律铁律：研究案例锚定企业总数封顶 6，不得再扩（2026-08-03 杜总定调）
    assert len(DEFAULT_CASES) == 6, f"预期 6 案例（封顶），实际 {len(DEFAULT_CASES)}"
    assert len(DEFAULT_CASES) <= 6, "❌ 违反范围纪律：锚定企业总数不得超过 6"


def test_p2a_global_anchors_scope_and_fields():
    """全球化锚：须标 scope=global + 价值链节点 + 完整事实与洞察（2026-08-03）。"""
    by_id = {c["case_id"]: c for c in DEFAULT_CASES}
    for cid in ("case_semicon_foundry_global_2026", "case_semicon_litho_global_2026"):
        c = by_id[cid]
        assert c["scope"] == "global", f"{cid} 缺 scope=global"
        assert c["value_chain_node"], f"{cid} 缺 value_chain_node"
        assert c["real_anchor"]
        assert len(c["disclosure_facts"]["facts"]) >= 10
        dims = {d["dimension"] for d in c["derived_insights"]}
        assert "strategy" in dims and len(dims) >= 3
    # 全球锚须与国内制造锚同属半导体，构成国际/国内对照组
    assert "半导体" in by_id["case_semicon_foundry_global_2026"]["industry"]
    assert "半导体" in by_id["case_semicon_2026"]["industry"]


def test_p2a_global_anchor_scrub_tokens():
    """全球锚真名片段须进擦洗表，且长 token 在前（防子串错洗）。"""
    toks = [a for a, _ in ANON_SCRUB_MAP]
    flat = " ".join(toks)
    for tok in ["台积电", "TSMC", "2330", "阿斯麦", "ASML"]:
        assert tok in flat, f"ANON_SCRUB_MAP 缺擦洗项 {tok}"
    assert toks.index("TSMC") < toks.index("TSM"), "TSMC 必须排在 TSM 之前，否则子串错洗"


def test_p2a_new_cases_have_required_fields():
    by_id = {c["case_id"]: c for c in DEFAULT_CASES}
    for cid in ("case_3c_2026", "case_newenergy_2026"):
        c = by_id[cid]
        assert c["real_anchor"], f"{cid} 缺 real_anchor"
        assert "disclosure_facts" in c and c["disclosure_facts"]["facts"]
        assert "derived_insights" in c and c["derived_insights"]
        # derived_insights 需含多维（至少含 strategy + equipment/cost 之一）
        dims = {d["dimension"] for d in c["derived_insights"]}
        assert "strategy" in dims
        assert len(dims) >= 3


def test_p2a_anon_scrub_map_has_new_anchors():
    flat = " ".join(a for a, _ in ANON_SCRUB_MAP)
    for tok in ["立讯精密", "002475", "宁德时代", "300750"]:
        assert tok in flat, f"ANON_SCRUB_MAP 缺擦洗项 {tok}"


@pytest.mark.asyncio
async def test_p2a_new_case_detail_external_no_leak():
    for cid in ("case_3c_2026", "case_newenergy_2026"):
        detail = await case_curator_agent.analyze(f"案例详情 {cid}")
        assert detail["status"] == "completed"
        assert "real_anchor" not in detail["case"]
        _assert_no_leak(detail, f"case_curator.detail[{cid}]")


@pytest.mark.asyncio
async def test_p2a_teaching_dual_version_internal_only_has_real_anchor():
    dual = await case_curator_agent.analyze("生成教学双版")
    assert dual["status"] == "completed"
    for d in dual["dual_versions"]:
        # 外部视图零真名
        _assert_no_leak(d["teaching_external"], "teaching_external")
        # 内部视图含 real_anchor（仅 internal 可见）
        assert d["teaching_internal"].get("real_anchor")


def test_p2b_equipment_categories_expanded():
    cats = equipment_profiles.EQUIPMENT_CATEGORIES
    # 3C 3 类 + 新能源 3 类 + 半导体 6 类 = 12 类
    for k in ("smt", "cnc", "injection", "coating", "winding", "formation"):
        assert k in cats, f"EQUIPMENT_CATEGORIES 缺 {k}"
    assert len(cats) == 12, f"预期 12 设备类，实际 {len(cats)}"


def test_p2b_equipment_profiles_expanded():
    eq = equipment_profiles.PROFILES
    for eid in ("smt_1", "cnc_1", "injection_1", "coating_1", "winding_1", "formation_1"):
        assert eid in eq, f"PROFILES 缺 {eid}"
    # 总数 = 半导体 9 + 3C 3 + 新能源 3 = 15
    assert len(eq) == 15, f"预期 15 台设备模板，实际 {len(eq)}"
    # 新能源化成分容柜能耗显著高于其他（验证数据合理性）
    assert eq["formation_1"].power_kw_avg > eq["smt_1"].power_kw_avg


def test_p2b_preset_summary_equipment_types_cover_new_industries():
    summary = get_preset_summary()
    types = set(summary["equipment_types"])
    for t in ("SMT 贴片机", "CNC 加工中心", "注塑机", "涂布机", "卷绕/叠片机", "化成分容柜"):
        assert t in types, f"preset_summary.equipment_types 缺 {t}"
    # 设备总数覆盖 15
    assert summary["equipment_count"] == 15


def test_p2b_industry_dimension_lookup():
    """预设层核心入口：选行业 → 拉该行业全部设备模板。"""
    ov = equipment_profiles.industry_overview()
    assert set(ov.keys()) == {"semiconductor", "3c", "new_energy"}
    assert ov["semiconductor"]["profile_count"] == 9
    assert ov["3c"]["profile_count"] == 3
    assert ov["new_energy"]["profile_count"] == 3
    # 反查行业
    assert equipment_profiles.get_industry("scanner_1") == "semiconductor"
    assert equipment_profiles.get_industry("smt_1") == "3c"
    assert equipment_profiles.get_industry("formation_1") == "new_energy"
    assert equipment_profiles.get_industry("__not_exist__") is None
    # 每类设备都归属到某个行业，无孤儿
    for code, cat in equipment_profiles.EQUIPMENT_CATEGORIES.items():
        assert cat.get("industry"), f"设备类 {code} 未归属行业"


def test_p2b_preset_summary_exposes_industry_breakdown():
    summary = get_preset_summary()
    assert summary["equipment_industry_count"] == 3
    by_ind = summary["equipment_by_industry"]
    assert by_ind["3c"]["industry_cn"].startswith("3C")
    # 三行业设备模板数之和 == 总数
    assert sum(v["profile_count"] for v in by_ind.values()) == summary["equipment_count"]
