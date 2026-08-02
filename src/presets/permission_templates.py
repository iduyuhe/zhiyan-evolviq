"""预设层 · 权限模板库（Permission Templates）

与设备库 / ERP 库 / MES 库**完全同构**的第四类预设：

    设备库   → 客户来了，同型号设备直接套模板接入
    ERP 库   → 客户来了，选 SAP/用友/金蝶 直接套接口
    MES 库   → 客户来了，选西门子/罗克韦尔 直接套接口
    权限库   → 客户来了，按岗位勾选，权限即刻配好   ← 本模块

价值：企业入驻时不必逐个用户手工配"能看哪些智能体"，
而是"选行业 → 选岗位 → 权限自动成型"，把配置周期从数天压到数分钟。

模板结构（对应 `src/runtime/authn/capability.CapabilityScope`）：
    {
      "label": 岗位中文名,
      "summary": 一句话职责,
      "allowed_agents": [可用智能体白名单],
      "read_only_agents": [仅可读、不可触发自主动作的智能体],
      "data_scope": {数据域限定，如 {"workshop": ["fab1"]}},
    }

铁律：
- 模板只做「收窄」，不放大 RBAC Role 给出的权限（二者取交集）。
- 未在模板中的岗位 / 未匹配的行业 → 回落 GENERIC_TEMPLATES → 再回落全放行，
  绝不因模板缺失把用户锁死（可用性优先，真隔离在租户①与角色②层）。
"""

from __future__ import annotations

from typing import Any

from src.runtime.authn.capability import BusinessRole, normalize_scope

# ---------------------------------------------------------------- 通用模板
# 与行业无关的岗位基线，任何行业未命中专属模板时回落到这里。

GENERIC_TEMPLATES: dict[str, dict[str, Any]] = {
    BusinessRole.DEVICE_ENGINEER.value: {
        "label": "设备工程师",
        "summary": "盯设备健康、预测维护、能耗与 OEE，不看财务与供应商价格",
        "allowed_agents": [
            "pm_maintenance", "oee_optimizer", "energy_carbon",
            "aoi_judge", "smt_changeover",
        ],
        "read_only_agents": ["energy_carbon"],
        "data_scope": {},
    },
    BusinessRole.PROCESS_ENGINEER.value: {
        "label": "工艺工程师",
        "summary": "盯良率、工艺缺陷、DFM 与新产导入，对设备只读",
        "allowed_agents": [
            "yield_analysis", "quality_trace", "dfm_check",
            "ipc_standard", "rd_npi", "pm_maintenance", "eco_change",
        ],
        "read_only_agents": ["pm_maintenance"],
        "data_scope": {},
    },
    BusinessRole.QUALITY_MANAGER.value: {
        "label": "质量经理",
        "summary": "盯质量追溯、合规体系、CAPA 与检验标准，可发起纠正措施",
        "allowed_agents": [
            "quality_trace", "compliance_q", "ipc_standard",
            "aoi_judge", "yield_analysis", "eco_change", "compliance_reviewer",
        ],
        "read_only_agents": ["yield_analysis"],
        "data_scope": {},
    },
    BusinessRole.SUPPLY_MANAGER.value: {
        "label": "供应链经理",
        "summary": "盯齐套、缺料、替代、仓储物流与供应商绩效，不看良率明细",
        "allowed_agents": [
            "supply_chain", "wms_logistics", "procurement_manage",
            "demand_order", "bom_selector", "aps_scheduler",
        ],
        "read_only_agents": ["aps_scheduler"],
        "data_scope": {},
    },
    BusinessRole.FINANCE_CONTROLLER.value: {
        "label": "财务成本控制",
        "summary": "盯制造成本、能耗成本、经营指标、商机报价，对生产类智能体只读",
        "allowed_agents": [
            "cost_analysis", "energy_carbon", "executive_cockpit",
            "procurement_manage", "demand_order", "bid_intel",
        ],
        "read_only_agents": ["procurement_manage", "demand_order", "bid_intel"],
        "data_scope": {},
    },
    BusinessRole.PLANT_MANAGER.value: {
        "label": "厂长/总经理",
        "summary": "全景视角——所有智能体可见，经营决策类可自主执行",
        "allowed_agents": ["*"],
        "read_only_agents": [],
        "data_scope": {},
    },
    BusinessRole.CUSTOM.value: {
        "label": "自定义岗位",
        "summary": "作用域完全由管理员手工指定（默认最小可用：只读经营驾驶舱）",
        "allowed_agents": ["executive_cockpit"],
        "read_only_agents": ["executive_cockpit"],
        "data_scope": {},
    },
}


# ---------------------------------------------------------------- 行业模板
# 行业专属覆盖（只写与通用模板的差异项，运行时做浅合并）。

PERMISSION_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    # 半导体 Fab——与设备库首版（6 类 9 台）配套
    "semiconductor_fab": {
        BusinessRole.DEVICE_ENGINEER.value: {
            "summary": "盯光刻/刻蚀/薄膜等 Fab 设备健康、腔体状态与 PM 窗口",
            "allowed_agents": [
                "pm_maintenance", "oee_optimizer", "energy_carbon",
                "yield_analysis",  # Fab 场景设备-良率强耦合，需可查
            ],
            "read_only_agents": ["yield_analysis", "energy_carbon"],
        },
        BusinessRole.PROCESS_ENGINEER.value: {
            "summary": "盯 Fab 工艺窗口、良率、缺陷根因与工程变更",
            "allowed_agents": [
                "yield_analysis", "quality_trace", "rd_npi",
                "eco_change", "pm_maintenance", "aps_scheduler",
            ],
            "read_only_agents": ["pm_maintenance", "aps_scheduler"],
        },
    },
    # 电子组装 / SMT
    "electronics_smt": {
        BusinessRole.DEVICE_ENGINEER.value: {
            "summary": "盯贴片机/回流焊/AOI 设备与换线效率",
            "allowed_agents": [
                "pm_maintenance", "smt_changeover", "aoi_judge",
                "oee_optimizer", "energy_carbon",
            ],
            "read_only_agents": ["energy_carbon"],
        },
        BusinessRole.PROCESS_ENGINEER.value: {
            "summary": "盯 DFM、IPC 标准、焊接工艺与 AOI 判定",
            "allowed_agents": [
                "dfm_check", "ipc_standard", "aoi_judge",
                "quality_trace", "bom_selector", "eco_change",
            ],
            "read_only_agents": ["bom_selector"],
        },
    },
    # 通讯设备制造（研究案例首例锚定所在行业）
    "telecom_equipment": {
        BusinessRole.SUPPLY_MANAGER.value: {
            "summary": "盯多层供应链齐套、国产替代与长周期物料风险",
            "allowed_agents": [
                "supply_chain", "procurement_manage", "bom_selector",
                "wms_logistics", "demand_order", "industry_research",
            ],
            "read_only_agents": ["industry_research"],
        },
        BusinessRole.PLANT_MANAGER.value: {
            "summary": "全景 + 行业研究视角",
            "allowed_agents": ["*"],
            "read_only_agents": [],
        },
    },
}


# ---------------------------------------------------------------- 查询接口


def list_business_roles() -> list[dict[str, Any]]:
    """列出全部岗位（前端下拉框用）。"""
    return [
        {
            "value": key,
            "label": tpl["label"],
            "summary": tpl["summary"],
            "agent_count": ("全部" if "*" in tpl["allowed_agents"] else len(tpl["allowed_agents"])),
        }
        for key, tpl in GENERIC_TEMPLATES.items()
    ]


def list_industries() -> list[str]:
    """列出已建行业专属权限模板的行业 key。"""
    return sorted(PERMISSION_TEMPLATES.keys())


def scope_for_business_role(business_role: str, industry: str | None = None) -> dict[str, Any]:
    """取某岗位（可选行业）的标准功能作用域。

    合并顺序：GENERIC_TEMPLATES[role] ← PERMISSION_TEMPLATES[industry][role]（浅覆盖）。
    未知岗位 → 全放行（不锁死用户）。
    """
    base = GENERIC_TEMPLATES.get(business_role)
    if base is None:
        return normalize_scope(None)
    merged = dict(base)
    if industry:
        override = PERMISSION_TEMPLATES.get(industry, {}).get(business_role)
        if override:
            merged.update(override)
    return normalize_scope({
        "allowed_agents": merged.get("allowed_agents", ["*"]),
        "read_only_agents": merged.get("read_only_agents", []),
        "data_scope": merged.get("data_scope", {}),
    })


def industry_template(industry: str) -> dict[str, dict[str, Any]]:
    """取某行业的完整岗位→作用域映射（企业入驻一次性开权用）。"""
    return {
        role: scope_for_business_role(role, industry=industry)
        for role in GENERIC_TEMPLATES
    }


def get_permission_summary() -> dict[str, Any]:
    """权限模板库摘要（并入预设层全景）。"""
    return {
        "business_role_count": len(GENERIC_TEMPLATES),
        "business_roles": [t["label"] for t in GENERIC_TEMPLATES.values()],
        "industry_template_count": len(PERMISSION_TEMPLATES),
        "industries": list_industries(),
        "note": "岗位勾选即配权：入驻时选行业+岗位，功能作用域自动成型（只缩不放，与 RBAC 取交集）",
    }
