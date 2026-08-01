"""预设库 / 研究案例库 只读 REST（#427）

给 Studio 的两个独立页提供数据源：
- GET /presets/library      设备预设库（3 行业 12 类 15 台）+ ERP/MES 预设概览
- GET /presets/library/{industry}   单行业设备模板明细（含 OPC-UA 标签/关键部件/能耗）
- GET /cases/library        研究案例库（对外匿名列表）
- GET /cases/library/{case_id}      单案例详情（匿名视图）

🔴 匿名铁律：本模块任何响应绝不输出 real_anchor（真实锚定企业名）。
   案例详情统一走 case_curator._case_detail()，该方法已剔除 real_anchor。
🔴 只读：不提供任何写入/修改入口，避免绕过 case_curator 的合规闸门。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.runtime.authn.deps import require_auth

presets_router = APIRouter(prefix="/presets", tags=["presets"])
cases_router = APIRouter(prefix="/cases", tags=["cases"])


# ──────────────────────────── 设备 / 系统预设库 ────────────────────────────


def _equipment_detail(p) -> dict:
    """EquipmentProfile → 前端可读 JSON（不暴露 dataclass 内部结构）。"""
    return {
        "equipment_id": p.equipment_id,
        "name": p.name,
        "type_cn": p.type_cn,
        "vendor": p.vendor,
        "model": p.model,
        "opcua_tag_count": len(p.opcua_tags),
        "opcua_tags": [
            {"tag": k, "default": v[0], "unit": v[1], "desc": v[2]}
            for k, v in p.opcua_tags.items()
        ],
        "key_parts": p.key_parts,
        "power_kw_avg": p.power_kw_avg,
        "power_kw_peak": p.power_kw_peak,
        "coolant_flow_lpm": p.coolant_flow_lpm,
        "mtbf_hours": p.mtbf_hours,
    }


@presets_router.get("/library", dependencies=[Depends(require_auth)])
async def get_preset_library() -> dict:
    """预设层全景：设备库（按行业分组）+ ERP 库 + MES 库 + 权限模板。"""
    from src.presets import get_preset_summary, erp_profiles, mes_profiles
    from src.agents.pm_maintenance import equipment_profiles

    summary = get_preset_summary()
    overview = equipment_profiles.industry_overview()

    industries = []
    for code, info in overview.items():
        profiles = equipment_profiles.list_by_industry(code)
        industries.append({
            "industry": code,
            "industry_cn": info["industry_cn"],
            "equipment_type_count": info["equipment_type_count"],
            "equipment_types": info["equipment_types"],
            "profile_count": info["profile_count"],
            "equipments": [
                {
                    "equipment_id": p.equipment_id,
                    "name": p.name,
                    "type_cn": p.type_cn,
                    "vendor": p.vendor,
                    "model": p.model,
                    "opcua_tag_count": len(p.opcua_tags),
                    "key_part_count": len(p.key_parts),
                    "power_kw_avg": p.power_kw_avg,
                    "mtbf_hours": p.mtbf_hours,
                }
                for p in profiles
            ],
        })

    return {
        "status": "ok",
        "equipment": {
            "industry_count": summary["equipment_industry_count"],
            "type_count": len(summary["equipment_types"]),
            "profile_count": summary["equipment_count"],
            "industries": industries,
        },
        "erp": {
            "count": summary["erp_count"],
            "items": [
                {
                    "key": k,
                    "name": v.name,
                    "vendor": v.vendor,
                    "version": v.version,
                    "interfaces": v.interfaces,
                    "data_domain_count": len(v.data_domains),
                    "agent_count": len(v.agent_mapping),
                }
                for k, v in erp_profiles.ERP_REGISTRY.items()
            ],
        },
        "mes": {
            "count": summary["mes_count"],
            "items": [
                {
                    "key": k,
                    "name": getattr(v, "name", k),
                    "vendor": getattr(v, "vendor", ""),
                    "version": getattr(v, "version", ""),
                    "interfaces": getattr(v, "interfaces", []),
                    "data_domain_count": len(getattr(v, "data_domains", {})),
                    "agent_count": len(getattr(v, "agent_mapping", {})),
                }
                for k, v in mes_profiles.MES_REGISTRY.items()
            ],
        },
        "permission": {
            "role_count": summary["permission_role_count"],
            "roles": summary["permission_roles"],
            "industries": summary["permission_industries"],
        },
        "coverage": summary["estimated_coverage"],
    }


@presets_router.get("/library/{industry}", dependencies=[Depends(require_auth)])
async def get_preset_industry(industry: str) -> dict:
    """单行业设备模板明细（OPC-UA 标签 / 关键部件 / 能耗 / MTBF）。"""
    from src.agents.pm_maintenance import equipment_profiles

    if industry not in equipment_profiles.INDUSTRY_EQUIPMENT_TYPES:
        raise HTTPException(status_code=404, detail=f"未知行业代码: {industry}")
    profiles = equipment_profiles.list_by_industry(industry)
    return {
        "status": "ok",
        "industry": industry,
        "industry_cn": equipment_profiles.INDUSTRY_LABELS.get(industry, industry),
        "profile_count": len(profiles),
        "equipments": [_equipment_detail(p) for p in profiles],
    }


# ──────────────────────────── 研究案例库 ────────────────────────────


@cases_router.get("/library", dependencies=[Depends(require_auth)])
async def get_case_library() -> dict:
    """研究案例库列表（对外匿名，绝不含 real_anchor）。"""
    from src.agents.case_curator.agent import case_curator_agent

    result = await case_curator_agent.analyze("案例库列表")
    return {
        "status": "ok",
        "case_count": result.get("case_count", 0),
        "active_case_id": result.get("active_case_id"),
        "cases": result.get("cases", []),
        "summary": result.get("summary", ""),
    }


@cases_router.get("/my")
async def get_my_case(u: dict = Depends(require_auth)) -> dict:
    """本租户绑定的研究案例（#429 研究案例租户登录后看到的"自家数据"）。

    与 /cases/library/{id} 的区别：本接口面向租户自身，额外返回
    disclosure_facts（公开披露事实）与 derived_insights（推演结论），
    让 telecom / semicon 租户登录后能直接看到本行业推演数据。

    🔴 仍不返回 real_anchor；且明确标注 data_origin=public_disclosure_derivation。
    """
    from src.agents.case_curator.agent import case_curator_agent
    from src.runtime.seed_case_tenants import TENANT_CASE_BINDING

    tenant_id = u.get("tenant_id", "")
    case_id = TENANT_CASE_BINDING.get(tenant_id)
    if not case_id:
        return {
            "status": "ok",
            "bound": False,
            "tenant_id": tenant_id,
            "summary": "本租户未绑定研究案例（仅研究案例租户具备该视图）",
        }
    case_curator_agent._ensure_seed()
    c = case_curator_agent._get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"绑定案例缺失: {case_id}")
    return {
        "status": "ok",
        "bound": True,
        "tenant_id": tenant_id,
        "tenant_kind": "research_case",
        "data_origin": "public_disclosure_derivation",
        "disclaimer": "本视图数据来源于公开披露信息推演，非企业内部真实数据，本租户亦非签约客户。",
        "case": {
            "case_id": c["case_id"],
            "subject_anon": c["subject_anon"],
            "industry": c["industry"],
            "recommended_interfaces": c.get("recommended_interfaces", []),
            "teaching_notes_anon": c.get("teaching_notes_anon", ""),
            "pilot_scenario": c.get("pilot_scenario"),
            "disclosure_facts": c.get("disclosure_facts", {}),
            "derived_insights": c.get("derived_insights", []),
            "status": c.get("status", "active"),
            "updated_at": c.get("updated_at", ""),
        },
    }


@cases_router.get("/library/{case_id}", dependencies=[Depends(require_auth)])
async def get_case_detail(case_id: str) -> dict:
    """单案例详情（匿名视图：subject_anon + 推荐接口 + 教学笔记 + 试点场景）。"""
    from src.agents.case_curator.agent import case_curator_agent

    case_curator_agent._ensure_seed()
    c = case_curator_agent._get_case(case_id)
    if not c:
        raise HTTPException(status_code=404, detail=f"未知案例: {case_id}")
    detail = case_curator_agent._case_detail(c)
    payload = detail.get("case", {})
    # 🔴 双保险：即使上游结构变动，也在出口再擦一次真名字段
    payload.pop("real_anchor", None)
    return {"status": "ok", "case": payload, "summary": detail.get("summary", "")}
