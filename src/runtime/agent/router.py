"""多Agent路由引擎——根据用户目标自动分派到合适的Agent

当前Agent阵容（14个）：
1. 供应链Agent (supply_chain) — 物料齐套检查、缺料预警、替代推荐
2. 设备维护Agent (pm_maintenance) — 设备健康诊断、预测维护
3. 良率分析Agent (yield_analysis) — 晶圆良率分析、缺陷定位
4. 质量追溯Agent (quality_trace) — 客诉溯源、根因分析
5. DFM检查Agent (dfm_check) — PCB可制造性自动审查
6. BOM选型Agent (bom_selector) — 元器件智能选型+替代推荐
7. OEE优化Agent (oee_optimizer) — 产线OEE监控与优化
8. ECO变更Agent (eco_change) — 工程变更影响分析
9. 换线Agent (smt_changeover) — SMT换线优化
10. AOI判定Agent (aoi_judge) — AOI误报智能过滤
11. IPC标准Agent (ipc_standard) — IPC标准辅助查询与缺陷判定
12. 计划排程Agent (aps_scheduler) — 生产排程、产能负荷、交期承诺
13. 能源碳ESG Agent (energy_carbon) — 能耗监控、碳排放核算、节能降碳
14. 制造成本Agent (cost_analysis) — 单位成本拆解、降本机会、报价支撑
"""

import importlib
import logging

logger = logging.getLogger(__name__)


# Agent 注册表：agent_name → (模块路径, 单例变量名)
# 惰性 import（在 execute_by_agent 内按需加载），未用到的 Agent 不会被导入。
# 所有 Agent 均实现统一契约 BaseAgent.analyze(goal) -> dict。
AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    "supply_chain": ("src.agents.supply_chain.agent", "supply_chain_agent"),
    "pm_maintenance": ("src.agents.pm_maintenance.agent", "pm_agent"),
    "yield_analysis": ("src.agents.yield_analysis.agent", "yield_agent"),
    "quality_trace": ("src.agents.quality_trace.agent", "quality_trace_agent"),
    "dfm_check": ("src.agents.dfm_check.agent", "dfm_agent"),
    "bom_selector": ("src.agents.bom_selector.agent", "bom_selector_agent"),
    "oee_optimizer": ("src.agents.oee_optimizer.agent", "oee_agent"),
    "eco_change": ("src.agents.eco_change.agent", "eco_agent"),
    "smt_changeover": ("src.agents.smt_changeover.agent", "smt_changeover_agent"),
    "aoi_judge": ("src.agents.aoi_judge.agent", "aoi_agent"),
    "ipc_standard": ("src.agents.ipc_standard.agent", "ipc_standard_agent"),
    # 经营决策大脑（P1 企业级）
    "aps_scheduler": ("src.agents.aps_scheduler.agent", "aps_agent"),
    "energy_carbon": ("src.agents.energy_carbon.agent", "energy_carbon_agent"),
    "cost_analysis": ("src.agents.cost_analysis.agent", "cost_agent"),
}


# Agent路由规则：关键词 → 目标Agent
# 注意：顺序敏感，越具体的Agent越靠前，避免被宽泛触发词截获。
ROUTING_RULES = [
    # DFM检查Agent触发词（放最前，避免被BOM选型/供应链截获）
    (["dfm", "可制造性", "焊盘间距", "线宽", "阻焊", "过孔", "设计审查", "制造风险"], "dfm_check"),
    # BOM选型Agent触发词（放在供应链之前，避免"替代料"被供应链的"替代"截获）
    (["选型", "替代料", "pin-to-pin", "兼容", "元器件推荐", "lifecycle", "eol", "nrnd", "alternative", "stm32", "gd32", "tps", "mcu选型"], "bom_selector"),
    # 供应链Agent触发词（去掉宽泛的"替代"，避免截获BOM选型；靠BOM/缺料/采购等触发）
    (["物料", "齐套", "缺料", "BOM", "库存", "PO", "采购", "供应", "硅片", "光刻胶", "靶材", "特气", "supply", "inventory"], "supply_chain"),
    # OEE优化Agent触发词（放在设备维护之前，避免"综合效率"被"设备"截获；去掉"停机"避免抢维护）
    (["oee", "产线效率", "可用率", "性能率", "综合效率", "六大损失", "换线效率"], "oee_optimizer"),
    # 设备维护Agent触发词
    (["设备", "维护", "保养", "故障", "光刻机", "刻蚀机", "沉积", "备件", "维修", "健康", "pm", "maintenance"], "pm_maintenance"),
    # 换线Agent触发词
    (["换线", "changeover", "smt", "料站", "feeder", "钢网", "贴装程序"], "smt_changeover"),
    # AOI判定Agent触发词
    (["aoi", "误报", "复判", "光学检测", "缺陷检测"], "aoi_judge"),
    # ECO变更Agent触发词
    (["eco", "ecn", "变更", "工程变更", "物料切换", "版本切换"], "eco_change"),
    # 质量追溯Agent触发词（放在良率前面）
    (["追溯", "trace", "客诉", "投诉", "根因", "root", "cause", "归因", "异常批次"], "quality_trace"),
    # IPC标准Agent触发词（增强：焊点/桥连/拒收/可接受）
    (["ipc", "标准", "判定", "检验规范", "class 1", "class 2", "class 3", "可接受性", "桥连", "焊点", "拒收", "可接受"], "ipc_standard"),
    # 计划排程Agent触发词（经营决策大脑）
    (["排程", "排产", "生产计划", "产能", "交期", "工单", "投料", "调度", "负荷", "aps", "scheduling", "ctp"], "aps_scheduler"),
    # 能源碳ESG Agent触发词（经营决策大脑）
    (["能耗", "能源", "碳", "碳排放", "碳足迹", "esg", "双碳", "节能", "绿电", "排放", "energy", "carbon"], "energy_carbon"),
    # 制造成本Agent触发词（经营决策大脑）
    (["成本", "制造成本", "降本", "报价", "毛利", "费用", "单位成本", "成本核算", "cost"], "cost_analysis"),
    # 良率分析Agent触发词（放最后，作为宽泛兜底）
    (["良率", "yield", "缺陷", "defect", "质量", "quality", "颗粒", "污染", "合格率", "不良"], "yield_analysis"),
]


def route_goal(goal: str) -> str:
    """根据目标文本路由到合适的Agent"""
    goal_lower = goal.lower()

    for keywords, agent_name in ROUTING_RULES:
        for kw in keywords:
            if kw.lower() in goal_lower:
                logger.info(f"[Router] '{kw}' → {agent_name}")
                return agent_name

    # 默认：供应链Agent
    return "supply_chain"


def get_agent(agent_name: str):
    """按名称惰性加载并返回 Agent 单例（实现 BaseAgent 契约）。"""
    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}")
    module_path, singleton_name = AGENT_REGISTRY[agent_name]
    module = importlib.import_module(module_path)
    return getattr(module, singleton_name)


async def execute_by_agent(agent_name: str, goal: str) -> dict:
    """调用指定 Agent 执行——统一走 BaseAgent.analyze(goal) 契约。

    所有 Agent（含历史上使用 analyze_goal+execute 的 supply_chain、
    使用 trace 的 quality_trace）都已提供 analyze() 适配器，因此这里
    不再需要为每个 Agent 写分支，注册表 + 统一调用即可。
    """
    agent = get_agent(agent_name)
    result = await agent.analyze(goal)
    result["agent"] = agent_name
    return result
