"""MCP 能力层联邦——统一注册 11 个 Agent 的 in-process 工具，对外暴露为 MCP 协议能力集。

设计要点（与 T4 收敛一致）：
- Agent 内部仍走 in-process 工具层（MVP 主路径不变）；本模块是「能力对外暴露层」。
- 每个 Agent 贡献其核心工具（query + action），经统一命名空间 `agent__method` 聚合。
- dispatch 按 `agent__method` 路由到对应 XTools 实例方法，参数通过 kwargs 传递。
- 不引入运行时 MCP 传输依赖到 Agent 内部，零韧性风险。
"""

import contextvars
import logging

from src.agents.aoi_judge.tools import AOITools
from src.agents.bom_selector.tools import BOMSelectorTools
from src.agents.dfm_check.tools import DFMTools
from src.agents.eco_change.tools import ECOTools
from src.agents.ipc_standard.tools import IPCStandardTools
from src.agents.oee_optimizer.tools import OEETools
from src.agents.pm_maintenance.tools import PMTools
from src.agents.quality_trace.tools import QualityTraceTools
from src.agents.smt_changeover.tools import SMTChangeoverTools
from src.agents.supply_chain.tools import SupplyChainTools
from src.agents.yield_analysis.tools import YieldTools

logger = logging.getLogger(__name__)

# 多租户上下文：dispatch 调用期间记录当前租户，供下游工具在需要时读取。
# （参考目录数据【物料/BOM/库存/PO】为平台级共享目录；租户上下文用于调用隔离与审计。）
current_tenant: contextvars.ContextVar = contextvars.ContextVar("zhiyan_tenant", default="default")


def get_current_tenant() -> str:
    """读取当前调用所属租户（工具内可用）。"""
    return current_tenant.get()

# 每个 Agent 的 in-process 工具实例（与运行时同一套实现）
_INSTANCES = {
    "supply_chain": SupplyChainTools(),
    "aoi_judge": AOITools(),
    "bom_selector": BOMSelectorTools(),
    "dfm_check": DFMTools(),
    "eco_change": ECOTools(),
    "ipc_standard": IPCStandardTools(),
    "oee_optimizer": OEETools(),
    "pm_maintenance": PMTools(),
    "quality_trace": QualityTraceTools(),
    "smt_changeover": SMTChangeoverTools(),
    "yield_analysis": YieldTools(),
}

# 工具注册表：name -> (agent, method, description, params)
# 命名空间：{agent}__{method}，如 supply_chain__get_bom
TOOL_REGISTRY = {
    # 供应链
    "supply_chain__get_bom": ("supply_chain", "get_bom_data", "获取BOM物料清单", {"bom_id": "string"}),
    "supply_chain__get_inventory": ("supply_chain", "get_inventory", "查询物料库存", {"material_codes": "array"}),
    "supply_chain__get_po": ("supply_chain", "get_po_data", "查询采购订单", {"material_codes": "array"}),
    "supply_chain__find_alternatives": ("supply_chain", "find_alternatives", "查找替代料方案", {"material_code": "string", "max_price_variation_pct": "number"}),
    "supply_chain__lock_inventory": ("supply_chain", "lock_inventory", "锁定库存（授权内）", {"material_code": "string", "qty": "integer", "session_id": "string"}),
    "supply_chain__supply_check": ("supply_chain", "get_bom_data", "执行齐套检查", {"bom_id": "string"}),
    # 设备维护
    "pm_maintenance__get_equipment_list": ("pm_maintenance", "get_equipment_list", "列出设备档案", {}),
    "pm_maintenance__get_equipment_health": ("pm_maintenance", "get_equipment_health", "设备健康分", {"equipment_id": "string"}),
    "pm_maintenance__get_parts_life": ("pm_maintenance", "get_parts_life", "部件寿命", {"equipment_id": "string"}),
    "pm_maintenance__create_pm_workorder": ("pm_maintenance", "create_pm_workorder", "生成PM工单", {"equipment_id": "string", "parts": "array", "reason": "string"}),
    # 良率分析
    "yield_analysis__get_product_list": ("yield_analysis", "get_product_list", "列出产品", {}),
    "yield_analysis__get_yield_data": ("yield_analysis", "get_yield_data", "良率数据", {"product_id": "string"}),
    "yield_analysis__get_defect_distribution": ("yield_analysis", "get_defect_distribution", "缺陷分布", {"product_id": "string"}),
    "yield_analysis__create_doe_experiment": ("yield_analysis", "create_doe_experiment", "生成DOE实验", {"product_id": "string", "defect_type": "string", "params": "array"}),
    # 质量追溯
    "quality_trace__get_case_list": ("quality_trace", "get_case_list", "列出案例", {}),
    "quality_trace__search_cases": ("quality_trace", "search_cases", "搜索案例", {"query": "string"}),
    "quality_trace__create_capa": ("quality_trace", "create_capa", "生成CAPA", {"case_id": "string", "actions": "array"}),
    # BOM选型
    "bom_selector__get_component": ("bom_selector", "get_component", "查询器件", {"part_no": "string"}),
    "bom_selector__get_alternatives": ("bom_selector", "get_alternatives", "替代料列表", {"part_no": "string"}),
    "bom_selector__submit_alt_approval": ("bom_selector", "submit_alt_approval", "提交替代审批", {"target": "string", "alt": "string", "reason": "string"}),
    # DFM检查
    "dfm_check__get_rules": ("dfm_check", "get_rules", "DFM规则", {}),
    "dfm_check__get_design_checks": ("dfm_check", "get_design_checks", "设计检查项", {}),
    "dfm_check__create_dfm_report": ("dfm_check", "create_dfm_report", "生成DFM报告", {"design_file": "string", "grade": "string"}),
    # ECO变更
    "eco_change__get_case_list": ("eco_change", "get_case_list", "列出ECO", {}),
    "eco_change__get_case": ("eco_change", "get_case", "ECO详情", {"eco_id": "string"}),
    "eco_change__create_eco_task": ("eco_change", "create_eco_task", "生成ECO任务", {"eco_id": "string"}),
    # IPC标准
    "ipc_standard__list_standards": ("ipc_standard", "list_standards", "列出IPC标准", {}),
    "ipc_standard__match_judgment": ("ipc_standard", "match_judgment", "IPC缺陷判定", {"query": "string"}),
    "ipc_standard__create_training_task": ("ipc_standard", "create_training_task", "生成培训任务", {"standard_id": "string", "topic": "string"}),
    # OEE优化
    "oee_optimizer__get_line_list": ("oee_optimizer", "get_line_list", "列出产线", {}),
    "oee_optimizer__get_line": ("oee_optimizer", "get_line", "产线详情", {"line_id": "string"}),
    "oee_optimizer__create_improvement_task": ("oee_optimizer", "create_improvement_task", "生成改善任务", {"line_id": "string", "focus": "string"}),
    # SMT换线
    "smt_changeover__get_line_config": ("smt_changeover", "get_line_config", "产线配置", {"line_id": "string"}),
    "smt_changeover__list_plan_keys": ("smt_changeover", "list_plan_keys", "换线计划列表", {}),
    "smt_changeover__create_changeover_plan": ("smt_changeover", "create_changeover_plan", "生成换线计划", {"plan_key": "string", "line_id": "string"}),
    # AOI判定
    "aoi_judge__get_line_result": ("aoi_judge", "get_line_result", "AOI线体结果", {"line_id": "string"}),
    "aoi_judge__list_line_ids": ("aoi_judge", "list_line_ids", "AOI线体列表", {}),
    "aoi_judge__create_threshold_optimization": ("aoi_judge", "create_threshold_optimization", "生成阈值优化", {"line_id": "string", "suggestions": "array"}),
}


def list_tools_specs() -> list[dict]:
    """返回所有联邦工具的描述（供 MCP list_tools / HTTP /mcp/tools 使用）。"""
    return [
        {"name": name, "agent": spec[0], "description": spec[2], "params": spec[3]}
        for name, spec in TOOL_REGISTRY.items()
    ]


def federation_summary() -> dict:
    """按 Agent 分组统计联邦工具（供 /mcp/federation 使用）。"""
    by_agent: dict[str, list] = {}
    for name, spec in TOOL_REGISTRY.items():
        by_agent.setdefault(spec[0], []).append(
            {"name": name, "description": spec[2], "params": spec[3]}
        )
    return {
        "agents": len(by_agent),
        "total_tools": len(TOOL_REGISTRY),
        "by_agent": by_agent,
    }


async def dispatch(tool_name: str, arguments: dict | None, tenant_id: str | None = None) -> dict:
    """按命名空间路由到对应 Agent 的 in-process 工具方法。

    事实锚点铁律：仅透传调用确定性工具，不改写任何业务数字。
    tenant_id：当前调用所属租户，写入上下文变量供工具读取（调用隔离/审计）。
    """
    spec = TOOL_REGISTRY.get(tool_name)
    if not spec:
        raise ValueError(f"Unknown MCP tool: {tool_name}")
    agent, method, _desc, _params = spec
    inst = _INSTANCES[agent]
    func = getattr(inst, method)
    token = current_tenant.set(tenant_id or "default")
    try:
        return await func(**(arguments or {}))
    finally:
        current_tenant.reset(token)
