"""Agent管理API——列出所有可用Agent"""

from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])

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
]


@router.get("")
async def list_agents():
    """列出所有可用的Agent"""
    return {"agents": AGENT_REGISTRY, "total": len(AGENT_REGISTRY)}
