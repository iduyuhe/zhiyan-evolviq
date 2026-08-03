"""P2 研究案例扩列 + 设备预设扩列测试（2026-07-31）

覆盖：
- P2-A 研究案例：案例库从 2 行业扩至 4 行业（通讯+半导体+3C+新能源）
  - DEFAULT_CASES 含 case_3c_2026 / case_newenergy_2026
  - ANON_SCRUB_MAP 含立讯精密/002475/宁德时代/300750 擦洗项
  - 对外视图（详情/列表/教学）零真名泄漏
  - 2026-08-03 杜总校正口径：每行业 国际(global)≤5 + 国内(domestic)≤5，合计≤10
    （非全局封顶 6）。半导体首批即拉满 10 强（国际5：台积电/阿斯麦/英伟达/三星/日月光；
    国内5：中芯国际/北方华创/豪威/兆易/长电）。
- P2-B 设备预设：设备库从半导体 6 类扩至 3 行业 12 类
  - EQUIPMENT_CATEGORIES 含 3C(SMT/CNC/注塑) + 新能源(涂布/卷绕/化成分容)
  - PROFILES 含 smt_1/cnc_1/injection_1/coating_1/winding_1/formation_1
  - presets.get_preset_summary() equipment_types 覆盖新行业设备类型

🔴 匿名铁律：LEAK_TOKENS 对一切外发结果断言零真名（与 compliance_reviewer 完全一致）。
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
# 与 compliance_reviewer.agent.LEAK_TOKENS 保持完全一致
LEAK_TOKENS = [
    "中兴", "000063", "ZTE", "zte",
    "中芯", "688981", "00981", "SMIC", "smic",
    "立讯", "002475", "Luxshare", "luxshare",
    "宁德", "300750", "CATL", "catl",
    # 2026-08-03 第二批（每行业 国际5+国内5）：半导体 7 家新锚
    "英伟达", "輝達", "NVIDIA", "nvidia", "NVDA", "黄仁勋", "黃仁勳", "Jensen Huang",
    "三星电子", "三星電子", "三星", "Samsung", "samsung", "005930",
    "日月光投控", "日月光", "ASE Technology", "ASEH", "3711",   # ⚠️ 绝无裸 ASE
    "北方华创", "002371", "NAURA", "naura", "芯源微",
    "豪威集团", "韦尔股份", "豪威", "韦尔", "603501", "OmniVision", "omnivision",
    "兆易创新", "兆易", "603986", "GigaDevice", "gigadevice",
    "长电科技", "长电微电子", "长电微", "长电", "600584", "JCET", "jcet", "晟碟",
]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


def test_p2a_case_count_four_industries():
    ids = {c["case_id"] for c in DEFAULT_CASES}
    assert "case_telecom_2026" in ids
    assert "case_semicon_2026" in ids          # 国内晶圆代工（中芯国际）
    assert "case_3c_2026" in ids
    assert "case_newenergy_2026" in ids
    # 2026-08-03 杜总定调：每行业 国际5 + 国内5 = 10 强（半导体首批拉满）
    # 国际 5 强
    for cid in ("case_semicon_foundry_global_2026",   # 台积电
                "case_semicon_litho_global_2026",     # 阿斯麦
                "case_semicon_design_global_2026",    # 英伟达
                "case_semicon_memory_global_2026",    # 三星电子
                "case_semicon_osat_global_2026"):     # 日月光
        assert cid in ids, f"缺国际锚 {cid}"
    # 国内 5 强（含中芯国际 + 4 家 2026-08-03 第二批）
    for cid in ("case_semicon_equipment_cn_2026",     # 北方华创
                "case_semicon_cis_cn_2026",           # 豪威集团
                "case_semicon_memory_cn_2026",        # 兆易创新
                "case_semicon_osat_cn_2026"):         # 长电科技
        assert cid in ids, f"缺国内锚 {cid}"

    # 🔴 每行业配额铁律（2026-08-03 杜总校正口径，非全局封顶）：
    # 每行业 国际(global)≤5 且 国内(domestic)≤5，合计≤10。分组键 = industry_key。
    by_key: dict = {}
    for c in DEFAULT_CASES:
        bucket = by_key.setdefault(c["industry_key"], {"global": 0, "domestic": 0, "other": 0})
        sc = c.get("scope")
        if sc == "global":
            bucket["global"] += 1
        elif sc == "domestic":
            bucket["domestic"] += 1
        else:
            bucket["other"] += 1
    for key, cnt in by_key.items():
        assert cnt["global"] <= 5, f"❌ {key} 国际锚超 5：{cnt['global']}"
        assert cnt["domestic"] <= 5, f"❌ {key} 国内锚超 5：{cnt['domestic']}"
        assert cnt["global"] + cnt["domestic"] <= 10, f"❌ {key} 合计超 10"

    # 半导体首批应已拉满 10（国际5 + 国内5）
    semi = by_key["semiconductor"]
    assert semi["global"] == 5, f"半导体国际锚应=5，实={semi['global']}"
    assert semi["domestic"] == 5, f"半导体国内锚应=5（含中芯国际），实={semi['domestic']}"
    assert semi["global"] + semi["domestic"] == 10, f"半导体合计应=10，实={semi['global'] + semi['domestic']}"


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
    # 第二批 7 家新锚：长 token 在前（防子串错洗）
    for tok in ["英伟达", "NVIDIA", "NVDA",
                "三星电子", "Samsung", "005930",
                "日月光投控", "日月光", "ASE Technology",
                "北方华创", "NAURA",
                "豪威集团", "韦尔股份", "OmniVision",
                "兆易创新", "GigaDevice",
                "长电科技", "JCET"]:
        assert tok in flat, f"ANON_SCRUB_MAP 缺第二批擦洗项 {tok}"
    # 长 token 排序纪律：长在前，短在后
    assert toks.index("三星电子") < toks.index("三星"), "三星电子 须排在 三星 之前"
    assert toks.index("日月光投控") < toks.index("日月光"), "日月光投控 须排在 日月光 之前"
    assert toks.index("豪威集团") < toks.index("豪威"), "豪威集团 须排在 豪威 之前"
    assert toks.index("韦尔股份") < toks.index("韦尔"), "韦尔股份 须排在 韦尔 之前"
    assert toks.index("兆易创新") < toks.index("兆易"), "兆易创新 须排在 兆易 之前"
    assert toks.index("长电科技") < toks.index("长电微电子") < toks.index("长电微") < toks.index("长电"), \
        "长电科技 > 长电微电子 > 长电微 > 长电 顺序错乱"


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


def test_p2a_semicon_anchors_have_scope_and_node():
    """半导体 10 强：每个锚必须含 scope(国际/国内) + value_chain_node + real_anchor。"""
    semi = [c for c in DEFAULT_CASES if c["industry_key"] == "semiconductor"]
    assert len(semi) == 10, f"半导体锚应=10，实={len(semi)}"
    for c in semi:
        assert c.get("scope") in ("global", "domestic"), f"{c['case_id']} 缺合法 scope"
        assert c.get("value_chain_node"), f"{c['case_id']} 缺 value_chain_node"
        assert c.get("real_anchor"), f"{c['case_id']} 缺 real_anchor（内部锚定）"


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


# ══════════════════════════════════════════════════════════════════════════
# 2026-08-03 「对外可见」阶段 · 案例库扩锚定（适度补缺）验收
# 通讯 / 3C / 新能源 各补到 5（国际3 + 国内2），共 +12；半导体不动。
# ══════════════════════════════════════════════════════════════════════════

def _count_scope(cases, key):
    bucket = {"global": 0, "domestic": 0, "other": 0}
    for c in cases:
        if c["industry_key"] != key:
            continue
        sc = c.get("scope")
        if sc == "global":
            bucket["global"] += 1
        elif sc == "domestic":
            bucket["domestic"] += 1
        else:
            bucket["other"] += 1
    return bucket


def test_p2c_benchmark_expansion_quota():
    """扩锚定后三行业配额：国际=3、国内=2（叠加既有国内锚），合计=5≤10；半导体仍满额不动。"""
    assert _count_scope(DEFAULT_CASES, "telecom") == {
        "global": 3, "domestic": 2, "other": 0}, "通讯应 国际3+国内2"
    assert _count_scope(DEFAULT_CASES, "consumer_electronics") == {
        "global": 3, "domestic": 2, "other": 0}, "3C 应 国际3+国内2"
    assert _count_scope(DEFAULT_CASES, "new_energy") == {
        "global": 3, "domestic": 2, "other": 0}, "新能源应 国际3+国内2"
    # 半导体保持满额（10），不受本次扩锚定影响
    semi = _count_scope(DEFAULT_CASES, "semiconductor")
    assert semi["global"] == 5 and semi["domestic"] == 5, "半导体须仍=10"


def test_p2c_new_anchor_ids_present_and_well_formed():
    ids = {c["case_id"] for c in DEFAULT_CASES}
    expected = [
        # 通讯（+4，叠既有中兴=国内2）：国际3 + 国内1新增
        "case_telecom_global_1_2026", "case_telecom_global_2_2026",
        "case_telecom_global_3_2026", "case_telecom_cn_2_2026",
        # 3C（+4，叠既成立讯=国内2）：国际3 + 国内1新增
        "case_3c_global_1_2026", "case_3c_global_2_2026",
        "case_3c_global_3_2026", "case_3c_cn_2_2026",
        # 新能源（+4，叠既有宁德=国内2）：国际3 + 国内1新增
        "case_newenergy_global_1_2026", "case_newenergy_global_2_2026",
        "case_newenergy_global_3_2026", "case_newenergy_cn_2_2026",
    ]
    for cid in expected:
        assert cid in ids, f"缺扩锚定 {cid}"
    # 每个新锚必须含内部真名（real_anchor）与对外匿名（subject_anon），且零真名泄漏
    by_id = {c["case_id"]: c for c in DEFAULT_CASES}
    for cid in expected:
        c = by_id[cid]
        assert c["real_anchor"], f"{cid} 缺 real_anchor（内部锚定）"
        assert c["subject_anon"] and "real_anchor" not in c["subject_anon"]
        _assert_no_leak(c["subject_anon"], f"subject_anon[{cid}]")
        assert c["scope"] in ("global", "domestic")
        assert c["industry_key"] in ("telecom", "consumer_electronics", "new_energy")

