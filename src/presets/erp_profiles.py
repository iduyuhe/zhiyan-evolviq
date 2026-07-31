# 制造业主流 ERP 预设模板库

"""ERP 系统预设定义。

每套 ERP 定义其数据接口方式、可消费的数据域、以及对应的 Agent 映射。
目标：覆盖中国制造业 90% 以上的 ERP 安装量。
"""

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class ErpProfile:
    """单套 ERP 系统的预设模板"""

    # ── 基础 ──
    name: str
    vendor: str
    version: str
    description: str
    # 典型覆盖行业
    typical_industries: List[str] = field(default_factory=list)

    # ── 数据接口方式 ──
    # database: 直接读数据库表
    # api: REST/SOAP API
    # file: 文件交换（CSV/XML/IDoc）
    interfaces: List[str] = field(default_factory=list)

    # ── 可用数据域 ──
    # 每个域包含：域名称、关键表/端点、描述
    data_domains: Dict[str, List[Dict]] = field(default_factory=dict)

    # ── 消费 Agent 映射 ──
    # agent_name → [数据域列表]
    agent_mapping: Dict[str, List[str]] = field(default_factory=dict)

    # ── 连接信息模板 ──
    # 连接参数示例（具体值由客户提供）
    connection_template: Dict = field(default_factory=dict)


# ── SAP S/4HANA ──────────────────────────────────────────────

SAP_S4 = ErpProfile(
    name="SAP S/4HANA",
    vendor="SAP",
    version="2023 / 2025",
    description="全球最大 ERP 系统，中国大型制造企业的标配",
    typical_industries=["汽车", "化工", "电子", "机械设备", "消费品"],
    interfaces=["api", "file"],
    data_domains={
        "finance": [
            {"table": "BKPF + BSEG", "desc": "会计凭证抬头+行项目", "key_fields": "BUKRS, BELNR, GJAHR"},
            {"table": "KNA1 + KNB1", "desc": "客户主数据+公司代码视图"},
            {"table": "LFA1 + LFB1", "desc": "供应商主数据+公司代码视图"},
        ],
        "controlling": [
            {"table": "COEP", "desc": "成本控制凭证（作业类型/成本要素）"},
            {"table": "COSS", "desc": "成本对象合计表"},
        ],
        "procurement": [
            {"table": "EKKN + EKPO", "desc": "采购订单抬头+行项目"},
            {"table": "MSEG + MKPF", "desc": "物料凭证（收货/发货/转储）"},
        ],
        "sales": [
            {"table": "VBAK + VBAP", "desc": "销售订单抬头+行项目"},
            {"table": "LIKP + LIPS", "desc": "交货单抬头+行项目"},
        ],
        "material": [
            {"table": "MARC", "desc": "工厂级物料视图（库存/采购/MRP 参数）"},
            {"table": "MBEW", "desc": "物料评估（标准价/移动平均价/上期价）"},
            {"table": "MAKT", "desc": "物料描述"},
        ],
        "bom": [
            {"table": "MAST + STPO + STKO", "desc": "物料 BOM：抬头+行项目+S070 汇总"},
        ],
        "production": [
            {"table": "AFKO + AFPO + AFRU", "desc": "生产订单/确认"},
            {"table": "AFVV + AFVC", "desc": "工艺路线/工序"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales", "material"],
        "cost_analysis": ["controlling", "material", "bom"],
        "supply_chain": ["procurement", "material"],
        "demand_order": ["sales", "production"],
    },
    connection_template={
        "method": "RFC (SAP Java Connector / BAPI REST)",
        "params": {"ashost": "<主机IP>", "sysnr": "00", "client": "800", "lang": "ZH"},
        "auth": "SAP Service User（只读）",
        "test_query": "BAPI_COMPANYCODE_GETLIST",
    },
)


# ── 用友 U8+ ────────────────────────────────────────────────

YY_U8 = ErpProfile(
    name="用友 U8+",
    vendor="用友网络",
    version="U8+ 16.x / U8 cloud",
    description="中国中小制造业 ERP 销量第一，超 200 万客户",
    typical_industries=["机械制造", "电子", "化工", "食品", "医药"],
    interfaces=["database", "api"],
    data_domains={
        "finance": [
            {"table": "GL_accvouch", "desc": "凭证及明细账"},
            {"table": "GL_accsum", "desc": "科目汇总表"},
            {"table": "Customer", "desc": "客户档案"},
            {"table": "Vendor", "desc": "供应商档案"},
        ],
        "procurement": [
            {"table": "PU_ArrivalVouchs", "desc": "采购到货单"},
            {"table": "PU_PO", "desc": "采购订单"},
        ],
        "sales": [
            {"table": "SO_SOMain", "desc": "销售订单主表"},
            {"table": "SO_SODetails", "desc": "销售订单子表"},
            {"table": "DispatchList", "desc": "发货单"},
        ],
        "inventory": [
            {"table": "CurrentStock", "desc": "现存量表"},
            {"table": "RDRecord", "desc": "出入库单"},
            {"table": "Inventory", "desc": "存货档案"},
        ],
        "bom": [
            {"table": "BOM_BOM", "desc": "物料清单主表"},
            {"table": "BOM_BOMOp", "desc": "物料清单子项"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "bom", "inventory"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "inventory"],
    },
    connection_template={
        "method": "SQL Server 直接连接（只读用户）",
        "params": {"host": "<DB IP>", "port": 1433, "database": "UFDATA_XXX_2025"},
        "auth": "SQL Server 只读账号",
        "test_query": "SELECT COUNT(*) FROM GL_accvouch",
    },
)


# ── 用友 YonSuite / U9 cloud ────────────────────────────────

YY_YONSUITE = ErpProfile(
    name="用友 YonSuite / U9 cloud",
    vendor="用友网络",
    version="YonSuite 2025 / U9 cloud 最新",
    description="用友云原生 ERP，定位中大型制造业；U9 cloud 面向离散制造",
    typical_industries=["机械制造", "汽车零部件", "电子", "装备制造"],
    interfaces=["api"],
    data_domains={
        "finance": [
            {"endpoint": "/yonbip/api/voucher", "desc": "凭证接口"},
            {"endpoint": "/yonbip/api/glbalance", "desc": "科目余额"},
        ],
        "procurement": [
            {"endpoint": "/yonbip/api/purchaseorder", "desc": "采购订单"},
            {"endpoint": "/yonbip/api/purchasearrive", "desc": "到货单"},
        ],
        "sales": [
            {"endpoint": "/yonbip/api/saleorder", "desc": "销售订单"},
            {"endpoint": "/yonbip/api/delivery", "desc": "发货单"},
        ],
        "inventory": [
            {"endpoint": "/yonbip/api/currentstock", "desc": "现存量"},
        ],
        "manufacture": [
            {"endpoint": "/yonbip/api/mo", "desc": "生产订单"},
            {"endpoint": "/yonbip/api/productstructure", "desc": "物料清单 BOM"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "inventory", "manufacture"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "manufacture"],
    },
    connection_template={
        "method": "REST API（YonBIP 开放平台）",
        "params": {"base_url": "https://<租户>.yonbip.com"},
        "auth": "OAuth 2.0 / appKey + appSecret",
        "test_query": "/yonbip/api/user/info",
    },
)


# ── 金蝶 K/3 WISE ────────────────────────────────────────────

KD_K3 = ErpProfile(
    name="金蝶 K/3 WISE",
    vendor="金蝶国际",
    version="K/3 WISE 16.x",
    description="中国中小企业 ERP 主力产品，制造企业安装量极大",
    typical_industries=["电子", "机械", "五金", "建材", "食品"],
    interfaces=["database"],
    data_domains={
        "finance": [
            {"table": "t_Voucher", "desc": "凭证表"},
            {"table": "t_Account", "desc": "科目表"},
            {"table": "t_ItemDetail", "desc": "核算项目明细"},
        ],
        "procurement": [
            {"table": "t_POOrderEntry", "desc": "采购订单分录"},
            {"table": "t_POReceiveEntry", "desc": "收料通知单"},
        ],
        "sales": [
            {"table": "t_SaleOrder", "desc": "销售订单"},
            {"table": "t_SaleStock", "desc": "销售出库单"},
        ],
        "inventory": [
            {"table": "t_ICItem", "desc": "物料主数据"},
            {"table": "t_ICInventory", "desc": "即时库存"},
            {"table": "t_ICBill", "desc": "仓存单据"},
        ],
        "bom": [
            {"table": "t_BOMGroup", "desc": "BOM 主表"},
            {"table": "t_BOMChild", "desc": "BOM 子项"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "inventory", "bom"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "inventory"],
    },
    connection_template={
        "method": "SQL Server 直接连接（只读用户）",
        "params": {"host": "<DB IP>", "port": 1433, "database": "AIS2025XXXX"},
        "auth": "SQL Server 只读账号",
        "test_query": "SELECT COUNT(*) FROM t_Voucher",
    },
)


# ── 金蝶 Cloud / 星空 ────────────────────────────────────────

KD_CLOUD = ErpProfile(
    name="金蝶 Cloud / 星空",
    vendor="金蝶国际",
    version="金蝶云·星空 / 苍穹",
    description="金蝶云原生 ERP，中大型企业市场快速增长",
    typical_industries=["电子", "机械", "医药", "食品", "化工"],
    interfaces=["api"],
    data_domains={
        "finance": [
            {"endpoint": "/api/finance/voucher", "desc": "凭证查询"},
            {"endpoint": "/api/finance/glbalance", "desc": "科目余额"},
        ],
        "procurement": [
            {"endpoint": "/api/scm/purchaseorder", "desc": "采购订单"},
        ],
        "sales": [
            {"endpoint": "/api/scm/saleorder", "desc": "销售订单"},
        ],
        "inventory": [
            {"endpoint": "/api/scm/currentstock", "desc": "即时库存"},
        ],
        "manufacture": [
            {"endpoint": "/api/mfg/worksheet", "desc": "生产工单"},
            {"endpoint": "/api/mfg/bom", "desc": "物料清单"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "inventory", "manufacture"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "manufacture"],
    },
    connection_template={
        "method": "REST API（金蝶开放网关）",
        "params": {"base_url": "https://<租户>.kdcloud.com"},
        "auth": "OAuth 2.0 / appKey + appSecret",
        "test_query": "/api/user/info",
    },
)


# ── Oracle EBS / Fusion ──────────────────────────────────────

ORACLE_EBS = ErpProfile(
    name="Oracle EBS / Fusion Cloud",
    vendor="Oracle",
    version="EBS R12 / Fusion Cloud 25A",
    description="全球大型 ERP，中国外企和大型集团常用",
    typical_industries=["汽车", "化工", "电子", "医药", "高科技"],
    interfaces=["api", "database"],
    data_domains={
        "finance": [
            {"table/endpoint": "GL_JE_HEADERS / gl/journalEntries", "desc": "总账凭证"},
            {"table/endpoint": "AP_INVOICES_ALL / ap/invoices", "desc": "应付发票"},
            {"table/endpoint": "AR_RECEIVABLE_APPLICATIONS_ALL / ar/receipts", "desc": "应收核销"},
        ],
        "procurement": [
            {"table/endpoint": "PO_HEADERS_ALL / po/orders", "desc": "采购订单"},
        ],
        "sales": [
            {"table/endpoint": "OE_ORDER_HEADERS_ALL / orders", "desc": "销售订单"},
            {"table/endpoint": "WSH_DELIVERY_DETAILS / shipping", "desc": "发货明细"},
        ],
        "inventory": [
            {"table/endpoint": "MTL_ONHAND_QUANTITIES / inventory/onhand", "desc": "可用库存"},
            {"table/endpoint": "MTL_SYSTEM_ITEMS_B / items", "desc": "物料主数据"},
        ],
        "bom": [
            {"table/endpoint": "BOM_BILL_OF_MATERIALS / bom", "desc": "物料清单"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "inventory", "bom"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "inventory"],
    },
    connection_template={
        "method": "REST API (Oracle Cloud) / DB Link (EBS 本地)",
        "params": {"base_url": "https://<租户>.fa.oraclecloud.com"},
        "auth": "OAuth 2.0 / JWT",
        "test_query": "/crmRestApi/resources/version",
    },
)


# ── 浪潮 GS/PS ──────────────────────────────────────────────

INSPUR_GS = ErpProfile(
    name="浪潮 GS / PS",
    vendor="浪潮国际",
    version="GS Cloud 8.0 / PS 10.x",
    description="中国大型国企 ERP 主力供应商之一",
    typical_industries=["机械制造", "电子", "化工", "医药", "军工"],
    interfaces=["api", "database"],
    data_domains={
        "finance": [
            {"table/endpoint": "GL_DETAIL / api/finance/gl", "desc": "总账明细"},
            {"table/endpoint": "FI_AP_DETAIL / api/finance/ap", "desc": "应付"},
            {"table/endpoint": "FI_AR_DETAIL / api/finance/ar", "desc": "应收"},
        ],
        "procurement": [
            {"table/endpoint": "PO_ORDER / api/scm/purchase", "desc": "采购订单"},
        ],
        "sales": [
            {"table/endpoint": "SO_ORDER / api/scm/sale", "desc": "销售订单"},
        ],
        "inventory": [
            {"table/endpoint": "INV_ONHAND / api/scm/inventory", "desc": "库存"},
        ],
        "bom": [
            {"table/endpoint": "MKT_BOM / api/manufacture/bom", "desc": "物料清单"},
        ],
    },
    agent_mapping={
        "executive_cockpit": ["finance", "sales"],
        "cost_analysis": ["finance", "inventory", "bom"],
        "supply_chain": ["procurement", "inventory"],
        "demand_order": ["sales", "inventory"],
    },
    connection_template={
        "method": "REST API / SQL Server",
        "params": {"base_url": "https://<租户>.cloud.inspur.com"},
        "auth": "API Token + clientId",
        "test_query": "/api/health",
    },
)


# ── 汇总注册表 ──────────────────────────────────────────────

ERP_REGISTRY: Dict[str, ErpProfile] = {
    "sap_s4": SAP_S4,
    "yy_u8": YY_U8,
    "yy_yonsuite": YY_YONSUITE,
    "kd_k3": KD_K3,
    "kd_cloud": KD_CLOUD,
    "oracle_ebs": ORACLE_EBS,
    "inspur_gs": INSPUR_GS,
}

# 覆盖度估算（中国制造业 ERP 市场）
# SAP + Oracle ≈ 30%（大型企业）
# 用友 U8+ ≈ 30%（中小企业第一）
# 金蝶 K/3 ≈ 20%
# 金蝶 Cloud + 用友 YonSuite ≈ 10%
# 浪潮 + 其他 ≈ 10%
# 本库 7 套覆盖约 90%+ 的市场安装量


def list_erp() -> Dict[str, str]:
    return {k: f"{v.vendor} {v.name} {v.version}" for k, v in ERP_REGISTRY.items()}


def get_erp(key: str) -> ErpProfile | None:
    return ERP_REGISTRY.get(key)
