"""无感转型三圈解锁地图（S2 v30.5 β，#310）

总纲 §3.5「无感转型」三圈解锁模型（commit ce37d49 定调）首次代码化：

  外圈（free）    仅公开信息（六路之⑥ environment），4 个 agent 免费可用
  中圈（middle）  外部信号 × 轻量内部数据——接入第 1 个内部数据源
                  （信任爬梯③ = tenant.gateway_config 非空）即解锁
  内圈（inner）   深度内部数据，私有化部署解锁（ZHIYAN_PRIVATE_DEPLOYMENT=1）

纪律（F4 红线）：价值驱动解锁、不推销——本模块只提供事实进度与下一步
说明文案，绝不产生弹窗/催付逻辑；前端相邻呈现。
解锁状态查询同时是 S3（γ 智能推荐）的转化埋点数据源。
"""

from __future__ import annotations

import os

# ---------- 三圈成员（24 agent 全集，与 agents_api.AGENT_REGISTRY 对齐） ----------

OUTER_AGENTS = ["executive_cockpit", "supply_chain", "procurement_manage", "compliance_q"]
MIDDLE_AGENTS = [
    "cost_analysis", "demand_order", "bom_selector", "rd_npi",
    # 研究案例范式 + 企业入驻 + 合规闸门：范式与治理类，启用后激活（2026-07-29 24 阵营补齐）
    "industry_research", "case_curator", "enterprise_onboarding", "compliance_reviewer",
]
INNER_AGENTS = [
    "pm_maintenance", "yield_analysis", "quality_trace", "dfm_check",
    "oee_optimizer", "eco_change", "smt_changeover", "aoi_judge",
    "ipc_standard", "aps_scheduler", "energy_carbon", "wms_logistics",
]

CIRCLES = [
    {
        "key": "outer",
        "label": "外圈 · 环境感知（免费）",
        "requirement": "注册即用——仅消费公开环境信号（政策/行情/对标）",
        "agents": OUTER_AGENTS,
    },
    {
        "key": "middle",
        "label": "中圈 · 外部×内部交叉",
        "requirement": "上传 1 份 BOM 或接入第 1 个内部数据源即解锁，同时免除免费额度限制",
        "agents": MIDDLE_AGENTS,
    },
    {
        "key": "inner",
        "label": "内圈 · 深度自治（私有化）",
        "requirement": "私有化部署，深度内部数据不出厂区",
        "agents": INNER_AGENTS,
    },
]

_CIRCLE_ORDER = {"outer": 0, "middle": 1, "inner": 2}

NEXT_STEP = {
    "outer": "上传 1 份 BOM（物料清单文件，不接系统、不进内网），或在「连接」页配置"
             "第 1 个内部数据源（网关），即可解锁中圈 8 个交叉分析 agent（+研究案例/案例库/企业入驻/合规闸门），"
             "并免除信号/解读免费额度——数据仍只读，不改动任何现有系统。",
    "middle": "预约私有化部署评估，解锁内圈 12 个深度自治 agent（设备维护/良率/排产等），"
              "全部数据不出厂区。",
    "inner": "已全部解锁——24 个 agent 全量可用。",
}


def _private_deployment() -> bool:
    return os.getenv("ZHIYAN_PRIVATE_DEPLOYMENT", "0") == "1"


def trust_ladder_reached(tenant_id: str) -> bool:
    """信任爬梯③单一语义源（#311 收敛）：

    达成条件二选一（总纲 §3.5 中圈=「外部×轻量内部数据」）：
    - 已配置网关（接入第 1 个内部数据源）
    - 已上传 1 份 BOM（轻量内部数据文件，不接系统不进内网）

    usage_meter 豁免与本模块圈层判定都引用此函数——两个系统永不矛盾。
    """
    try:
        from src.runtime.tenant_store import tenant_store

        if tenant_store.get_gateway_config(tenant_id):
            return True
    except Exception:
        pass
    try:
        from src.runtime.bom_store import bom_store

        if bom_store.has_bom(tenant_id):
            return True
    except Exception:
        pass
    return False


def current_circle(tenant_id: str) -> str:
    """当前圈层判定（事实进度，与 usage_meter 豁免逻辑同源语义）。"""
    if _private_deployment():
        return "inner"
    if trust_ladder_reached(tenant_id):
        return "middle"  # 信任爬梯③：已接内部数据源或已上传 BOM
    return "outer"


def progress_view(tenant_id: str) -> dict:
    """三圈解锁进度视图（GET /environment/unlock-progress 消费）。"""
    circle = current_circle(tenant_id)
    rank = _CIRCLE_ORDER[circle]
    circles = []
    unlocked_agents = 0
    for c in CIRCLES:
        unlocked = _CIRCLE_ORDER[c["key"]] <= rank
        if unlocked:
            unlocked_agents += len(c["agents"])
        circles.append({**c, "unlocked": unlocked, "agent_count": len(c["agents"])})
    return {
        "tenant_id": tenant_id,
        "current_circle": circle,
        "circles": circles,
        "unlocked_agents": unlocked_agents,
        "total_agents": sum(len(c["agents"]) for c in CIRCLES),
        "next_step": NEXT_STEP[circle],
    }
