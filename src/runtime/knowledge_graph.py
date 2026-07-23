"""知识图谱构建与查询——跨 11 个 Agent 的工业语义网

设计要点：
- 数据源：data/seed/*.json（11 个 Agent 的种子数据）
- 实体/关系：跨 Agent 共享节点（Product / Equipment / Line / DefectType / Component / Material）
  桥接各域，形成一张联邦语义网
- 事实锚点铁律：仅抽取/写入实体与关系，绝不改写任何业务数字或动作
- 底层存储由 neo4j_client 原语抽象（Neo4j / 内存图 双模式）
- apply_execution_result：Agent 执行后增量写入（如锁定替代、开 CAPA），仅基于确定性结果
"""

import json
import logging
import os
from typing import Optional

from src.common import neo4j_client as neo

logger = logging.getLogger(__name__)

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "seed")


def _load(name: str) -> Optional[object]:
    path = os.path.join(SEED_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"种子 {name} 加载失败：{e}")
        return None


# 设备类型关键词（用于质量案例 → PM 设备桥接）
_EQUIP_KEYWORDS = ["光刻机", "刻蚀机", "薄膜沉积", "涂布", "显影", "清洗", "离子注入", "CMP"]


def _match_equipment(name: str, equipments: list[dict]) -> Optional[str]:
    """从质量案例 suspected_equipments 名称提取类型关键词，匹配 PM 设备。"""
    for eq in equipments:
        etype = eq.get("type", "")
        if etype and etype in name:
            return eq.get("equipment_id")
    return None


async def build_from_seeds() -> dict:
    """从种子数据构建跨 Agent 知识图谱。返回 stats。"""
    await neo.clear_graph()

    # ===== 供应链域：BOM / 物料 / 库存 / PO =====
    for bom_file in ("bom_npi_007.json", "smic_bom.json"):
        bom = _load(bom_file)
        if not bom:
            continue
        bom_id = bom.get("bom_id")
        product_name = bom.get("product_name")
        bom_nid = f"BOM:{bom_id}"
        prod_nid = f"PROD:{product_name}"
        await neo.merge_node("Bom", bom_nid, {"bom_id": bom_id, "product_name": product_name})
        await neo.merge_node("Product", prod_nid, {"name": product_name})
        await neo.merge_edge(bom_nid, prod_nid, "产出")
        mats = bom.get("materials") or []
        for m in mats:
            code = m.get("code")
            if not code:
                continue
            mat_nid = f"MAT:{code}"
            await neo.merge_node("Material", mat_nid, {
                "code": code, "name": m.get("name"), "category": m.get("category"),
                "supplier": m.get("supplier"), "lead_time_days": m.get("lead_time_days"),
                "price": m.get("price"),
            })
            await neo.merge_edge(bom_nid, mat_nid, "包含", {"qty": m.get("qty")})
        # SMIC BOM 无 materials 字段，用 items 建物料
        if not mats:
            for it in bom.get("items", []):
                code = it.get("material_code")
                if not code:
                    continue
                mat_nid = f"MAT:{code}"
                await neo.merge_node("Material", mat_nid, {
                    "code": code, "name": it.get("name"), "qty_per_bom": it.get("qty"),
                })
                await neo.merge_edge(bom_nid, mat_nid, "包含", {"qty": it.get("qty")})

    # 库存（写入 Material 属性）
    for inv_file in ("inventory.json", "smic_inventory.json"):
        inv = _load(inv_file)
        if not isinstance(inv, dict):
            continue
        for code, v in inv.items():
            await neo.merge_node("Material", f"MAT:{code}", {
                "code": code, "stock_on_hand": v.get("on_hand"), "stock_reserved": v.get("reserved"),
            })

    # PO
    for po_file in ("po_data.json", "smic_po.json"):
        pos = _load(po_file)
        if isinstance(pos, list):
            for p in pos:
                po_id = p.get("po")
                code = p.get("material_code")
                if not po_id or not code:
                    continue
                po_nid = f"PO:{po_id}"
                await neo.merge_node("PO", po_nid, {
                    "po": po_id, "qty": p.get("qty"), "expected": p.get("expected"), "status": p.get("status"),
                })
                await neo.merge_edge(po_nid, f"MAT:{code}", "供应", {
                    "qty": p.get("qty"), "status": p.get("status"), "expected": p.get("expected"),
                })

    # ===== BOM 选型 / 替代料 =====
    comp = _load("components.json")
    if comp and isinstance(comp, dict):
        for pn, c in comp.get("components", {}).items():
            await neo.merge_node("Component", f"CMP:{pn}", {
                "part_no": pn, "category": c.get("category"), "manufacturer": c.get("manufacturer"),
                "lead_time_days": c.get("lead_time_days"), "unit_price_usd": c.get("unit_price_usd"),
            })
        for pn, alts in comp.get("alternatives_map", {}).items():
            for a in alts:
                await neo.merge_edge(f"CMP:{pn}", f"CMP:{a}", "可替代", {"alt_part": a})

    # ===== 设备域（PM）=====
    pm = _load("pm_equipment.json")
    equipments = (pm or {}).get("equipments", [])
    for eq in equipments:
        eq_id = eq.get("equipment_id")
        if not eq_id:
            continue
        eq_nid = f"EQP:{eq_id}"
        await neo.merge_node("Equipment", eq_nid, {
            "equipment_id": eq_id, "name": eq.get("name"), "type": eq.get("type"),
            "vendor": eq.get("vendor"), "location": eq.get("location"),
            "health_score": eq.get("health_score"), "status": eq.get("status"),
        })
        for part in eq.get("key_parts", []):
            pno = part.get("part_no")
            if not pno:
                continue
            part_nid = f"PART:{pno}"
            await neo.merge_node("Part", part_nid, {
                "part_no": pno, "name": part.get("name"),
                "life_remaining_pct": part.get("life_remaining_pct"), "risk": part.get("risk"),
            })
            await neo.merge_edge(eq_nid, part_nid, "有部件", {
                "life_remaining_pct": part.get("life_remaining_pct"), "risk": part.get("risk"),
            })
        for i, alert in enumerate(eq.get("recent_alerts", [])):
            if alert:
                await neo.merge_node("Alert", f"ALERT:{eq_id}:{i}", {"text": alert, "equipment": eq_id})
                await neo.merge_edge(eq_nid, f"ALERT:{eq_id}:{i}", "发生告警")

    # ===== 质量域 =====
    qt = _load("quality_trace.json")
    for case in (qt or {}).get("cases", []):
        cid = case.get("id")
        if not cid:
            continue
        case_nid = f"CASE:{cid}"
        await neo.merge_node("DefectCase", case_nid, {
            "id": cid, "product": case.get("product"), "issue": case.get("issue"),
            "severity": case.get("severity"), "affected_qty": case.get("affected_qty"),
        })
        prod = case.get("product")
        if prod:
            await neo.merge_edge(case_nid, f"PROD:{prod}", "涉及产品")
        for sus in case.get("suspected_equipments", []):
            eq_id = _match_equipment(sus.get("name", ""), equipments)
            if eq_id:
                await neo.merge_edge(case_nid, f"EQP:{eq_id}", "怀疑设备", {"match_score": sus.get("match_score")})
        rc = case.get("root_cause", "") or ""
        for eq in equipments:
            for part in eq.get("key_parts", []):
                if part.get("name") and part.get("name") in rc:
                    await neo.merge_edge(case_nid, f"PART:{part.get('part_no')}", "根因部件")

    # ===== 良率域 =====
    yd = _load("yield_data.json")
    for p in (yd or {}).get("products", []):
        pid = p.get("product_id") or p.get("name")
        if not pid:
            continue
        prod_nid = f"PROD:{p.get('name')}"
        await neo.merge_node("Product", prod_nid, {"name": p.get("name"), "node": p.get("node")})
        y_nid = f"YIELD:{pid}"
        await neo.merge_node("YieldRecord", y_nid, {
            "product_id": pid, "current_yield": p.get("current_yield"), "target_yield": p.get("target_yield"),
        })
        await neo.merge_edge(prod_nid, y_nid, "有良率")
        for dt in p.get("defect_top3", []):
            dt_name = dt if isinstance(dt, str) else (dt.get("name") if isinstance(dt, dict) else None)
            if dt_name:
                await neo.merge_node("DefectType", f"DT:{dt_name}", {"name": dt_name})
                await neo.merge_edge(prod_nid, f"DT:{dt_name}", "有缺陷")

    # ===== IPC 标准域 =====
    ipc = _load("ipc_standards.json")
    if ipc and isinstance(ipc, dict):
        for sid, s in ipc.get("standards", {}).items():
            await neo.merge_node("Standard", f"STD:{sid}", {
                "standard_id": sid, "title": s.get("title") if isinstance(s, dict) else None,
            })
        for qe in ipc.get("query_examples", []):
            cat = qe.get("matched_category")
            if cat:
                await neo.merge_node("DefectType", f"DT:{cat}", {"name": cat})
                await neo.merge_edge(f"STD:{qe.get('matched_standard')}", f"DT:{cat}", "判定")

    # ===== ECO 域 =====
    eco = _load("eco_cases.json")
    if eco and isinstance(eco, dict):
        for eid, e in eco.get("cases", {}).items():
            eco_nid = f"ECO:{eid}"
            await neo.merge_node("ECOCase", eco_nid, {"eco_id": eid, "title": e.get("title"), "type": e.get("type")})
            cd = e.get("change_detail", {})
            for pn in (cd.get("old_part"), cd.get("new_part")):
                if pn:
                    await neo.merge_edge(eco_nid, f"CMP:{pn}", "变更器件")
            for line in e.get("affected_routings", []):
                await neo.merge_edge(eco_nid, f"LINE:{line}", "影响产线")

    # ===== DFM 域 =====
    dfm = _load("dfm_check.json")
    if dfm and isinstance(dfm, dict):
        design = dfm.get("design_file")
        design_nid = f"DESIGN:{design}" if design else None
        if design_nid:
            await neo.merge_node("Design", design_nid, {"file": design})
        for chk in dfm.get("design_checks", []):
            rid = chk.get("rule_id")
            if rid:
                await neo.merge_node("Rule", f"RULE:{rid}", {"rule_id": rid, "status": chk.get("status")})
                if design_nid:
                    await neo.merge_edge(f"RULE:{rid}", design_nid, "应用于")

    # ===== OEE / SMT / AOI 域（共享 Line 节点）=====
    oee = _load("oee_lines.json")
    if oee and isinstance(oee, dict):
        for lid, l in oee.get("lines", {}).items():
            await neo.merge_node("Line", f"LINE:{lid}", {"line_id": lid})
            await neo.merge_node("OEERecord", f"OEE:{lid}", {
                "line_id": lid, "oee": l.get("oee") if isinstance(l, dict) else None,
            })
            await neo.merge_edge(f"LINE:{lid}", f"OEE:{lid}", "有OEE")
    smt = _load("smt_changeover.json")
    if smt and isinstance(smt, dict):
        for lid in smt.get("line_config", {}):
            await neo.merge_node("Line", f"LINE:{lid}", {"line_id": lid})
        for key, plan in smt.get("changeover_plans", {}).items():
            await neo.merge_node("Changeover", f"CHO:{key}", {"key": key})
            lid = plan.get("line_id") if isinstance(plan, dict) else None
            if lid:
                await neo.merge_edge(f"LINE:{lid}", f"CHO:{key}", "有换线")
    aoi = _load("aoi_results.json")
    if aoi and isinstance(aoi, dict):
        for lid in aoi.get("results", {}):
            await neo.merge_node("Line", f"LINE:{lid}", {"line_id": lid})
            await neo.merge_node("AOIResult", f"AOI:{lid}", {"line_id": lid})
            await neo.merge_edge(f"LINE:{lid}", f"AOI:{lid}", "有AOI")

    return await neo.graph_stats()


async def apply_execution_result(tenant_id: str, agent_name: str, session_id: str, result: dict) -> None:
    """Agent 执行后增量写入图谱（仅基于确定性结果，事实锚点铁律）。

    写入的节点/关系均带 tenant 属性，使知识图谱按租户隔离：
    同租户的执行数据可经 /kg/query?tenant=... 精确查询，互不可见。
    """
    try:
        if agent_name == "supply_chain":
            for act in result.get("actions_taken", []) or []:
                if act.get("type") == "lock_alternative":
                    old = act.get("material_code") or act.get("old_material")
                    alt = act.get("alt_code") or act.get("alternative_code")
                    if old and alt:
                        await neo.merge_edge(f"MAT:{old}", f"MAT:{alt}", "锁定替代",
                                             {"session_id": session_id, "status": act.get("status"), "tenant": tenant_id})
        elif agent_name == "quality_trace":
            for act in result.get("actions_taken", []) or []:
                if act.get("type") == "create_capa":
                    cid = act.get("case_id")
                    if cid:
                        await neo.merge_node("CAPA", f"CAPA:{cid}", {"case_id": cid, "tenant": tenant_id})
                        await neo.merge_edge(f"CASE:{cid}", f"CAPA:{cid}", "已开CAPA", {"tenant": tenant_id})
    except Exception as e:
        logger.warning(f"图谱增量写入失败（不破管）：{e}")


async def rebuild() -> dict:
    return await build_from_seeds()
