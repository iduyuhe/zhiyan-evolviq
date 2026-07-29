"""Agent管理API——列出所有可用Agent"""

import logging

from fastapi import APIRouter

from src.runtime.agent.router import AGENT_REGISTRY as _ROUTER_AGENT_REGISTRY

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

AGENT_REGISTRY = [
    {
        "id": "supply_chain",
        "name": "供应链自治Agent",
        "description": "物料齐套检查、缺料预警、替代方案推荐、授权内自主执行",
        "status": "active",
        "version": "1.0.0",
        "scenarios": ["物料齐套检查", "缺料预警", "替代推荐", "国产替代评估"],
        "icon": "📦",
    },
    {
        "id": "pm_maintenance",
        "name": "设备预测维护Agent",
        "description": "半导体设备健康诊断、预测维护建议、关键部件寿命管理",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["设备健康评分", "预测维护", "备件更换预警"],
        "icon": "🔧",
    },
    {
        "id": "yield_analysis",
        "name": "良率分析Agent",
        "description": "晶圆良率趋势分析、缺陷分类统计、根因定位、改进建议",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["良率趋势", "缺陷分析", "设备-良率关联"],
        "icon": "📈",
    },
    {
        "id": "quality_trace",
        "name": "质量追溯Agent",
        "description": "晶圆质量根因追溯，客诉→批次→工艺→设备→参数的端到端分析",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["客诉追溯", "根因分析", "缺陷定位", "纠正措施"],
        "icon": "🔍",
    },
    {
        "id": "dfm_check",
        "name": "DFM检查Agent",
        "description": "PCB/PCBA可制造性设计自动审查，焊盘间距/线宽/过孔/阻焊规则校验",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["焊盘间距检查", "线宽校验", "阻焊覆盖", "组件布局审查", "DFM评审报告"],
        "icon": "📐",
    },
    {
        "id": "bom_selector",
        "name": "BOM选型Agent",
        "description": "元器件智能选型+替代推荐，兼容性分析/价格趋势/供应链稳定性评估",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["pin-to-pin替代", "国产替代推荐", "成本优化", "EOL预警"],
        "icon": "🔬",
    },
    {
        "id": "oee_optimizer",
        "name": "OEE优化Agent",
        "description": "产线OEE实时监控，可用率×性能率×质量率三要素分析+六大损失分析",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["OEE计算", "六大损失分析", "瓶颈识别", "改善建议"],
        "icon": "⚡",
    },
    {
        "id": "eco_change",
        "name": "ECO变更Agent",
        "description": "工程变更指令影响分析，受影响BOM/WIP/库存/工序识别+跨部门协同",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["变更影响分析", "在制库存评估", "行动项分发", "风险评级"],
        "icon": "🔄",
    },
    {
        "id": "smt_changeover",
        "name": "SMT换线Agent",
        "description": "SMT换线优化与料站预配置，SMED分析+关键路径+检查清单",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["换线计划", "料站预配", "SMED优化", "换线检查清单"],
        "icon": "🔀",
    },
    {
        "id": "aoi_judge",
        "name": "AOI判定Agent",
        "description": "AOI误报智能过滤，误报根因分析+检测阈值优化+复判工时节省",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["误报率分析", "阈值优化", "缺陷分类", "复判效率"],
        "icon": "👁",
    },
    {
        "id": "ipc_standard",
        "name": "IPC标准Agent",
        "description": "IPC标准辅助查询与缺陷判定，Class 1/2/3分级+检验方法推荐",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["标准查询", "缺陷判定", "Class分级", "检验方法"],
        "icon": "📋",
    },
    {
        "id": "aps_scheduler",
        "name": "计划排程Agent",
        "description": "生产排程、产能负荷、交期承诺(CTP)与工单优先级优化",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["生产排程", "产能负荷", "交期承诺", "工单优先级", "瓶颈识别"],
        "icon": "🧠",
    },
    {
        "id": "energy_carbon",
        "name": "能源碳ESG Agent",
        "description": "能耗监控、碳排放/碳足迹核算、ESG合规与节能降碳机会",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["能耗监控", "碳排放核算", "碳强度", "绿电比例", "节能机会", "ESG"],
        "icon": "🌿",
    },
    {
        "id": "cost_analysis",
        "name": "制造成本Agent",
        "description": "单位制造成本拆解（材料/人工/设备/能源/良率）、降本机会与报价支撑",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["成本核算", "成本拆解", "降本机会", "毛利率", "报价支撑"],
        "icon": "💰",
    },
    {
        "id": "demand_order",
        "name": "需求订单Agent",
        "description": "需求预测、订单履约率、未交付风险与产销协同(S&OP)供给再平衡",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["需求预测", "订单履约", "未交付风险", "产销协同", "S&OP"],
        "icon": "📊",
    },
    {
        "id": "wms_logistics",
        "name": "仓储物流Agent",
        "description": "库存健康度、库容利用、物流时效与在途监控，授权内自动补货",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["库存健康", "安全库存", "物流时效", "呆滞占比", "自动补货"],
        "icon": "🚚",
    },
    {
        "id": "compliance_q",
        "name": "质量合规Agent",
        "description": "质量体系认证跟踪、审核发现闭环、法规合规(RoHS/REACH)与CAPA管理",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["认证管理", "审核发现", "法规合规", "CAPA", "体系认证"],
        "icon": "🛡️",
    },
    {
        "id": "executive_cockpit",
        "name": "经营驾驶舱Agent",
        "description": "经营KPI看板、预算执行、产出追踪、现金流与利润分析——全厂决策支持",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["经营KPI", "预算执行", "产出追踪", "现金流", "利润分析"],
        "icon": "🏢",
    },
    {
        "id": "rd_npi",
        "name": "研发新产导入Agent",
        "description": "NPI项目全生命周期管理、里程碑跟踪、批量试产与风险识别",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["NPI项目", "里程碑", "项目风险", "批量试产", "产品导入"],
        "icon": "🔬",
    },
    {
        "id": "procurement_manage",
        "name": "采购与供应商管理Agent",
        "description": "供应商绩效评分（交期/质量/成本/合规）、合同管理与采购策略",
        "status": "active",
        "version": "0.1.0",
        "scenarios": ["供应商绩效", "合同管理", "采购策略", "供应商评审", "战略采购"],
        "icon": "📑",
    },
    {
        "id": "industry_research",
        "name": "行业研究 Agent",
        "description": "研究案例范式发动机：选行业标杆→匿名画像→调度外圈 4 agent 推演→对齐真实锚定出校准报告",
        "status": "active",
        "version": "1.0.0",
        "scenarios": ["行业标杆选择", "匿名画像构建", "外圈 agent 协同推演", "真实锚定校准"],
        "icon": "🏛️",
    },
    {
        "id": "case_curator",
        "name": "案例库策展 Agent",
        "description": "案例库活体本体：列/汇总案例、挂载推荐接口、生成教学双版（对外匿名/对内真名）",
        "status": "active",
        "version": "1.0.0",
        "scenarios": ["案例库列表", "案例查询", "推荐接口挂载", "教学双版生成"],
        "icon": "📚",
    },
    {
        "id": "enterprise_onboarding",
        "name": "企业入驻 Agent",
        "description": "两阶段实例化入口：解读企业现状画像→基于案例库推荐接口→输出三态开通清单并映射三圈解锁",
        "status": "active",
        "version": "1.0.0",
        "scenarios": ["现状画像解析", "接口推荐", "三态开通清单", "三圈解锁引导"],
        "icon": "🏭",
    },
    {
        "id": "compliance_reviewer",
        "name": "合规闸门 Agent",
        "description": "研究案例范式合规审查：匿名/真名双版边界 + 零真名泄漏 + research_case 纪律校验",
        "status": "active",
        "version": "1.0.0",
        "scenarios": ["匿名边界审查", "真名泄漏复核", "research_case 纪律校验"],
        "icon": "✅",
    },
]


def _align_with_router():
    """启动期一次性：把 router 已注册但静态元数据缺失的 agent 自动补占位（防再失同步）。
    静态元数据已为新增 agent 显式补充；本函数作为安全网，对未来新增 agent 兜底。
    """
    known = {a["id"] for a in AGENT_REGISTRY}
    for name in _ROUTER_AGENT_REGISTRY:
        if name not in known:
            AGENT_REGISTRY.append({
                "id": name,
                "name": name.replace("_", " ").title() + " Agent",
                "description": "（元数据待补，自动占位）",
                "status": "active",
                "version": "0.0.0",
                "scenarios": [],
                "icon": "🤖",
            })
            logger.warning("agents_api: agent '%s' 在 router 已注册但元数据缺失，已插入占位", name)


_align_with_router()


@router.get("")
async def list_agents():
    """列出所有可用的 Agent"""
    return {"agents": AGENT_REGISTRY, "total": len(AGENT_REGISTRY)}
