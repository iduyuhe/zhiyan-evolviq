"""多Agent路由引擎——根据用户目标自动分派到合适的Agent

当前Agent阵容（11个）：
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
"""

import logging

logger = logging.getLogger(__name__)


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


async def execute_by_agent(agent_name: str, goal: str) -> dict:
    """调用指定Agent执行"""
    if agent_name == "supply_chain":
        from src.agents.supply_chain.agent import supply_chain_agent
        plan = await supply_chain_agent.analyze_goal(goal)
        result = await supply_chain_agent.execute(goal, plan)
        result["agent"] = "supply_chain"
        return result

    elif agent_name == "pm_maintenance":
        from src.agents.pm_maintenance.agent import pm_agent
        result = await pm_agent.analyze(goal)
        result["agent"] = "pm_maintenance"
        return result

    elif agent_name == "yield_analysis":
        from src.agents.yield_analysis.agent import yield_agent
        result = await yield_agent.analyze(goal)
        result["agent"] = "yield_analysis"
        return result

    elif agent_name == "quality_trace":
        from src.agents.quality_trace.agent import quality_trace_agent
        result = await quality_trace_agent.trace(goal)
        result["agent"] = "quality_trace"
        return result

    elif agent_name == "dfm_check":
        from src.agents.dfm_check.agent import dfm_agent
        result = await dfm_agent.analyze(goal)
        result["agent"] = "dfm_check"
        return result

    elif agent_name == "bom_selector":
        from src.agents.bom_selector.agent import bom_selector_agent
        result = await bom_selector_agent.analyze(goal)
        result["agent"] = "bom_selector"
        return result

    elif agent_name == "oee_optimizer":
        from src.agents.oee_optimizer.agent import oee_agent
        result = await oee_agent.analyze(goal)
        result["agent"] = "oee_optimizer"
        return result

    elif agent_name == "eco_change":
        from src.agents.eco_change.agent import eco_agent
        result = await eco_agent.analyze(goal)
        result["agent"] = "eco_change"
        return result

    elif agent_name == "smt_changeover":
        from src.agents.smt_changeover.agent import smt_changeover_agent
        result = await smt_changeover_agent.analyze(goal)
        result["agent"] = "smt_changeover"
        return result

    elif agent_name == "aoi_judge":
        from src.agents.aoi_judge.agent import aoi_agent
        result = await aoi_agent.analyze(goal)
        result["agent"] = "aoi_judge"
        return result

    elif agent_name == "ipc_standard":
        from src.agents.ipc_standard.agent import ipc_standard_agent
        result = await ipc_standard_agent.analyze(goal)
        result["agent"] = "ipc_standard"
        return result

    else:
        raise ValueError(f"Unknown agent: {agent_name}")
