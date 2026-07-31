# 制造业主流 MES 预设模板库

"""MES 系统预设定义。

每套 MES 定义其数据接口方式、可消费的生产/品质/设备数据域、以及对应 Agent 映射。
覆盖中国半导体/SMT/电子/机械制造行业 85%+ 的主流 MES 系统。
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class MesProfile:
    """单套 MES 系统的预设模板"""

    # ── 基础 ──
    name: str
    vendor: str
    version: str
    description: str
    typical_industries: List[str] = field(default_factory=list)

    # ── 数据接口方式 ──
    interfaces: List[str] = field(default_factory=list)

    # ── 可用数据域 ──
    # production: 生产执行（工单/WIP/报工）
    # quality: 品质检测（检验/良率/缺陷）
    # equipment: 设备状态（运行/待机/停机/维护）
    # material: 物料追溯/消耗
    data_domains: Dict[str, List[Dict]] = field(default_factory=dict)

    # ── 消费 Agent 映射 ──
    agent_mapping: Dict[str, List[str]] = field(default_factory=dict)

    # ── 连接模板 ──
    connection_template: Dict = field(default_factory=dict)


# ── 西门子 Opcenter ──────────────────────────────────────────

SIEMENS_OPCENTER = MesProfile(
    name="西门子 Opcenter",
    vendor="Siemens",
    version="Opcenter Execution 2025",
    description="全球最大 MES（原 Siemens SIMATIC IT），离散/流程制造全覆盖",
    typical_industries=["汽车", "电子", "医药", "食品", "化工"],
    interfaces=["api", "database"],
    data_domains={
        "production": [
            {"endpoint/table": "/api/workorder", "desc": "生产工单"},
            {"endpoint/table": "/api/wip/tracking", "desc": "在制品跟踪"},
            {"endpoint/table": "/api/production/confirmation", "desc": "生产报工/完工确认"},
        ],
        "quality": [
            {"endpoint/table": "/api/quality/inspection", "desc": "检验批次"},
            {"endpoint/table": "/api/quality/yield", "desc": "良率/缺陷统计"},
            {"endpoint/table": "/api/quality/spc", "desc": "SPC 控制图数据"},
        ],
        "equipment": [
            {"endpoint/table": "/api/equipment/status", "desc": "设备实时状态"},
            {"endpoint/table": "/api/equipment/oee", "desc": "OEE 数据"},
            {"endpoint/table": "/api/equipment/downtime", "desc": "停机记录"},
        ],
        "material": [
            {"endpoint/table": "/api/material/trace", "desc": "物料追溯链"},
            {"endpoint/table": "/api/material/consumption", "desc": "物料消耗记录"},
        ],
    },
    agent_mapping={
        "pm_maintenance": ["equipment"],
        "energy_carbon": ["equipment", "production"],
        "quality_trace": ["quality"],
        "yield_analysis": ["quality"],
        "demand_order": ["production", "material"],
    },
    connection_template={
        "method": "REST API (Opcenter Open API) / OPC-UA 复合",
        "params": {"base_url": "https://<主机>/opcenter/api"},
        "auth": "OAuth 2.0 / Bearer Token",
        "test_query": "/api/health",
    },
)


# ── 罗克韦尔 FactoryTalk ────────────────────────────────────

ROCKWELL_FT = MesProfile(
    name="罗克韦尔 FactoryTalk",
    vendor="Rockwell Automation",
    version="FactoryTalk ProductionCentre 2025",
    description="北美最大 MES，在中国汽车/电子行业有大量存量安装",
    typical_industries=["汽车", "电子", "食品", "化工", "半导体"],
    interfaces=["api", "opcua"],
    data_domains={
        "production": [
            {"endpoint/table": "/FTW/WorkOrders", "desc": "工单管理"},
            {"endpoint/table": "/FTW/WIPTracking", "desc": "WIP 跟踪"},
            {"endpoint/table": "/FTW/ProductionSummary", "desc": "生产汇总"},
        ],
        "quality": [
            {"endpoint/table": "/FTW/Inspections", "desc": "检验数据"},
            {"endpoint/table": "/FTW/YieldReport", "desc": "良率报告"},
        ],
        "equipment": [
            {"endpoint/table": "OPC-UA ns=2;s=Line*.Status", "desc": "产线/设备状态"},
            {"endpoint/table": "OPC-UA ns=2;s=Line*.OEE", "desc": "OEE"},
            {"endpoint/table": "/FTW/DowntimeEvents", "desc": "停机事件"},
        ],
        "material": [
            {"endpoint/table": "/FTW/MaterialTrace", "desc": "物料追溯"},
        ],
    },
    agent_mapping={
        "pm_maintenance": ["equipment"],
        "energy_carbon": ["equipment"],
        "quality_trace": ["quality"],
        "yield_analysis": ["quality"],
        "demand_order": ["production", "material"],
    },
    connection_template={
        "method": "REST API + OPC-UA 双通道",
        "params": {"api_url": "https://<主机>/FTW/api", "opcua_endpoint": "opc.tcp://<主机>:4840"},
        "auth": "Windows AD / API Key",
        "test_query": "/FTW/api/version",
    },
)


# ── 霍尼韦尔 MES ────────────────────────────────────────────

HONEYWELL_MES = MesProfile(
    name="霍尼韦尔 MES",
    vendor="Honeywell",
    version="Honeywell MES 2025 / POMS",
    description="过程行业最强 MES，化工/制药/炼油/半导体行业占据显著份额",
    typical_industries=["化工", "制药", "炼油", "半导体", "冶金"],
    interfaces=["api", "opcua"],
    data_domains={
        "production": [
            {"endpoint/table": "/api/ProdOrders", "desc": "生产指令"},
            {"endpoint/table": "/api/EProcedure", "desc": "电子批记录"},
            {"endpoint/table": "/api/Campaign", "desc": "生产批次汇总"},
        ],
        "quality": [
            {"endpoint/table": "/api/QCSample", "desc": "质检取样"},
            {"endpoint/table": "/api/SPC", "desc": "实时 SPC 数据"},
        ],
        "equipment": [
            {"endpoint/table": "OPC-UA ns=2;s=Unit*.Status", "desc": "单元设备状态"},
            {"endpoint/table": "/api/EquipmentHistory", "desc": "设备运行历史"},
        ],
        "material": [
            {"endpoint/table": "/api/MaterialBalance", "desc": "物料平衡"},
        ],
    },
    agent_mapping={
        "pm_maintenance": ["equipment"],
        "energy_carbon": ["equipment"],
        "quality_trace": ["quality"],
        "yield_analysis": ["quality"],
    },
    connection_template={
        "method": "REST API + OPC-UA",
        "params": {"api_url": "https://<主机>/mes/api"},
        "auth": "OAuth 2.0 + Client Certificate",
        "test_query": "/api/health",
    },
)


# ── 国产 MES 代表 × 3 ─────────────────────────────────────

# 注：国产 MES 市场极为分散，此处取 3 家最具代表性厂商
# 实际对接时按具体产品映射标签，架构不变

CN_MES_GENERIC = MesProfile(
    name="国产 MES（通用模板）",
    vendor="多家（明匠/华磊/元工/佰思杰/外部定制等）",
    version="通用模板 V1",
    description="国产 MES 通用预设——适用于采用 SQL Server/MySQL + REST API 的国产 MES",
    typical_industries=["电子", "机械", "五金", "家电", "装备"],
    interfaces=["database", "api"],
    data_domains={
        "production": [
            {"table/endpoint": "work_order / api/workorder", "desc": "生产工单"},
            {"table/endpoint": "wip_record / api/wip", "desc": "在制品记录"},
            {"table/endpoint": "report_hourly / api/report", "desc": "时报工/产报"},
        ],
        "quality": [
            {"table/endpoint": "inspection_record / api/quality", "desc": "检验记录"},
            {"table/endpoint": "defect_record / api/defect", "desc": "缺陷记录"},
        ],
        "equipment": [
            {"table/endpoint": "equip_status / api/equipment/status", "desc": "设备状态"},
            {"table/endpoint": "equip_downtime / api/equipment/downtime", "desc": "设备停机"},
        ],
    },
    agent_mapping={
        "pm_maintenance": ["equipment"],
        "quality_trace": ["quality"],
        "yield_analysis": ["quality"],
        "demand_order": ["production"],
    },
    connection_template={
        "method": "根据实际 MES 产品选择：SQL Server / MySQL / REST API",
        "params": {"db_type": "mysql|sqlserver", "host": "<DB IP>", "port": 3306},
        "auth": "只读数据库用户",
        "test_query": "SELECT COUNT(*) FROM work_order",
    },
)

# ── 头部国产 MES 特定厂商 ──
# 某些行业的头部定制 MES 可单独建模板

CN_MES_SPECIFIC = [
    {
        "vendor": "赛意信息 MES（华为生态）",
        "industries": ["电子", "通信设备"],
        "features": ["华为云原生", "与华为 FusionPlant 深度集成"],
        "data_method": "REST API + 华为云 IoT 双通道",
    },
    {
        "vendor": "鼎捷 MES（原神州数码 MES）",
        "industries": ["电子", "机械", "五金"],
        "features": ["与金蝶/用友 ERP 预集成", "离散制造场景强"],
        "data_method": "SQL Server + REST API",
    },
    {
        "vendor": "华磊迅拓 MES（半导体/电子行业）",
        "industries": ["半导体", "电子", "SMT"],
        "features": ["半导体行业专用", "SECS/GEM 预集成"],
        "data_method": "REST API + SECS/GEM",
    },
]


def list_mes() -> Dict[str, str]:
    reg = {
        "siemens_opcenter": "西门子 Opcenter Execution",
        "rockwell_ft": "罗克韦尔 FactoryTalk",
        "honeywell_mes": "霍尼韦尔 MES / POMS",
        "cn_mes_generic": "国产 MES 通用模板",
    }
    for spec in CN_MES_SPECIFIC:
        reg[f"cn_mes_{spec['vendor'][:4]}"] = spec["vendor"]
    return reg


MES_REGISTRY: Dict[str, MesProfile] = {
    "siemens_opcenter": SIEMENS_OPCENTER,
    "rockwell_ft": ROCKWELL_FT,
    "honeywell_mes": HONEYWELL_MES,
    "cn_mes_generic": CN_MES_GENERIC,
}
