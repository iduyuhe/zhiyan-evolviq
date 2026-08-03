"""案例库策展 Agent——拥有案例库活体本体（§3.7，2026-07-29 杜总定调）

案例库是产品活体本体、行业分析资产、教学素材、获客内容引擎。
本 Agent 负责案例库版本化、推荐接口挂载、教学双版生成（对外匿名 / 对内真名）。

🔴 匿名铁律：对外输出(teaching_external 视图)严禁含真实锚定公司名；
real_anchor 仅存案例内部字段，进入 teaching_internal 视图，绝不进 teaching_external。
"""

import json
import logging
import os

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

CASE_STORE_PATH = os.path.join(os.path.dirname(__file__), "cases.json")

# 🔴 匿名擦洗映射（研究案例外发前统一擦洗；长 token 在前，防子串错洗）
# 所有 real_anchor 相关真名/代码片段 → 匿名替代；industry_research._sanitize 消费。
ANON_SCRUB_MAP = [
    # 通讯·中兴
    ("中兴通讯", "某某通讯公司"),
    ("中兴", "某通讯厂商"),
    ("000063", "***"),
    ("ZTE", "***"),
    ("zte", "***"),
    # 半导体·中芯
    ("中芯国际", "某某半导体公司"),
    ("中芯", "某半导体厂"),
    ("688981", "***"),
    ("00981", "***"),
    ("SMIC", "FAB-X"),
    ("smic", "fab-x"),
    # 3C 精密制造·立讯精密（2026-07-31 研究案例扩列）
    ("立讯精密", "某某精密制造公司"),
    ("立讯", "某精密制造商"),
    ("002475", "***"),
    ("Luxshare", "***"),
    ("luxshare", "***"),
    # 新能源·宁德时代（2026-07-31 研究案例扩列）
    ("宁德时代", "某某新能源公司"),
    ("宁德", "某新能源厂商"),
    ("300750", "***"),
    ("CATL", "***"),
    ("catl", "***"),
    # 半导体·全球晶圆代工龙头（2026-08-03 杜总定调：第一批全球化锚，总数封顶 6）
    ("台积电", "某某全球晶圆代工龙头"),
    ("台積電", "某某全球晶圆代工龙头"),
    ("TSMC", "GLOBAL-FOUNDRY-A"),
    ("tsmc", "global-foundry-a"),
    ("TSM", "***"),  # 须在 "TSMC" 之后，防子串错洗
    ("2330", "***"),
    ("魏哲家", "***"),
    # 半导体·全球光刻设备龙头（2026-08-03）
    ("阿斯麦", "某某全球光刻设备公司"),
    ("阿斯麥", "某某全球光刻设备公司"),
    ("ASML", "GLOBAL-LITHO-A"),
    ("asml", "global-litho-a"),
    ("Fouquet", "***"),
    ("傅恪礼", "***"),
]

# 🔴 案例种子（先有后优；2026-07-29 杜总两批定调：
#   ①通讯·中兴通讯（研究案例首例）
#   ②半导体·中芯国际（P3 首客试点，场景 A=设备健康/能耗孪生））
# real_anchor 仅内部可见；subject_anon 对外呈现。
DEFAULT_CASES = [
    {
        "case_id": "case_telecom_2026",
        "subject_anon": "某某通讯公司（研究案例·公开披露）",
        "industry": "通讯设备 / 信息通信",
        "real_anchor": "中兴通讯（000063.SZ）",  # 🔴 内部锚定真实上市公司，仅 internal 视图
        "recommended_interfaces": [
            "industry_research",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "cost_analysis",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」如何在通讯行业标杆企业推演 "
            "战略 / 供应链 / 合规 / 成本四维，并对外匿名、对内真名双版教学。"
        ),
        "teaching_notes_internal": (
            "内部锚定中兴通讯(000063.SZ)公开披露，用于校准行业研究推演；"
            "真实公司名仅在本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-07-29",
        "disclosure_facts": {
            "source": "2025 年年度报告（2026-03-06 披露；公司官网 / 上证报 / 证券日报交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业总收入", "value": "1339.0 亿元", "yoy": "+10.4%"},
                {"metric": "归母净利润", "value": "56.2 亿元", "yoy": "-33.32%（高基数+结构因素，非经营恶化）"},
                {"metric": "扣非归母净利润", "value": "33.7 亿元", "yoy": "—"},
                {"metric": "研发费用", "value": "227.6 亿元", "yoy": "占营收 17.0%"},
                {"metric": "现金分红比例", "value": "占归母净利润 35%", "yoy": "—"},
                {"metric": "运营商网络营收", "value": "628.6 亿元", "yoy": "-10.62%（国内承压）", "share": "46.9%"},
                {"metric": "政企业务营收", "value": "372.2 亿元", "yoy": "+100.5%（翻番，增长引擎）", "share": "27.8%"},
                {"metric": "消费者业务营收", "value": "338.2 亿元", "yoy": "+4.4%", "share": "25.26%"},
                {"metric": "算力业务营收", "value": "同比 +150%", "yoy": "占整体 24.6%"},
                {"metric": "服务器及存储营收", "value": "同比 +200%+", "yoy": "—"},
                {"metric": "数据中心产品营收", "value": "同比 +50%", "yoy": "—"},
                {"metric": "国内营收", "value": "897.4 亿元", "yoy": "+9.4%", "share": "67.0%"},
                {"metric": "国际营收", "value": "441.6 亿元", "yoy": "+12.4%", "share": "33.0%"},
                {"metric": "毛利率", "value": "阶段性承压", "yoy": "行业周期切换+业务结构变化"},
                {"metric": "战略主轴", "value": "连接+算力 双轮驱动 / AI 全栈", "yoy": "—"},
                {"metric": "全球地位", "value": "5G 基站/核心网/固网 全球第二；FWA&MBB 份额全球第一；PON CPE 发货全球第一", "yoy": "—"},
                {"metric": "智算落地", "value": "全球 500+ 绿色数据中心、万卡级智算中心；智算服务器进入互联网/电信/金融/电力头部核心场景", "yoy": "—"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "算力业务已成第二增长引擎，增长结构从运营商单一驱动转向'运营商基本盘 + 政企/算力新引擎'双轮。",
                "rationale": "算力营收同比 +150%、占整体 24.6%；政企业务（算力主力）同比 +100.5% 翻番成为整体增长引擎；与'连接+算力'双轮驱动战略自洽。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["同比 +150%", "占整体 24.6%", "+100.5%"],
            },
            {
                "dimension": "strategy",
                "claim": "表观净利下滑主要为基数与结构因素，盈利质量未恶化，经营韧性增强。",
                "rationale": "归母 56.2 亿同比 -33.32% 主因上年一次性收益高基数 + 毛利率阶段性承压；但营收重回增长 +10.4%、扣非 33.7 亿、研发占比 17% 高强度，非基本面恶化。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["-33.32%", "+10.4%", "17.0%"],
            },
            {
                "dimension": "supply_chain",
                "claim": "自研芯片 + 韧性供应链是算力 TCO 优势核心壁垒，对抗价格竞争加剧。",
                "rationale": "年报强调整合芯片/算法/架构/交付/标准五大能力，纵向自研是毛利率承压下维持 TCO 最优的关键护城河。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["17.0%", "阶段性承压"],
            },
            {
                "dimension": "supply_chain",
                "claim": "运营商国内承压倒逼供应链需求向政企与海外'大国大T'迁移，需调整产能与采购布局。",
                "rationale": "运营商国内受通信基础设施投资下降影响营收 -10.62%；国际 +12.4%、政企 +100.5%，供应链客户结构随之迁移。",
                "assertion_type": "descriptive",
                "value_judgment": "medium",
                "key_figures": ["-10.62%", "+12.4%", "+100.5%"],
            },
            {
                "dimension": "compliance",
                "claim": "全球市场准入与地缘贸易合规是核心持续性风险面。",
                "rationale": "国际占 33%、坚定'大国大T'战略与全球交付；出海依赖全球市场准入，出口管制与地缘合规为持续性风险。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["33.0%"],
            },
            {
                "dimension": "cost",
                "claim": "毛利率阶段性承压源于业务结构切换，非成本失控；降本应聚焦算力供应链 TCO 与政企交付效率。",
                "rationale": "毛利率承压来自行业周期 + 算力/政企占比上升的结构性现象；成本改善方向应为算力供应链协同与交付效率，而非一刀切压制造本。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["阶段性承压", "占整体 24.6%"],
            },
        ],
    },
    {
        "case_id": "case_semicon_2026",
        "subject_anon": "某某半导体公司（研究案例·公开披露）",
        "industry": "半导体 / 集成电路晶圆代工",
        "real_anchor": "中芯国际（688981.SH / 00981.HK）",  # 🔴 内部锚定，仅 internal 视图
        "pilot_scenario": {
            "scenario": "A",
            "label": "设备健康 / 能耗孪生",
            "agents": ["pm_maintenance", "energy_carbon"],
            "decided_at": "2026-07-29",
            "note": "P3 首客试点场景（杜总定调）；按铁律接口就位不实测，真实数据接入后 ZHIYAN_DEMO_DATA=0 起跳。",
        },
        "recommended_interfaces": [
            "industry_research",
            "pm_maintenance",
            "energy_carbon",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "cost_analysis",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」在半导体晶圆代工标杆企业上推演 "
            "设备健康 / 能耗孪生（P3 首客试点场景 A），并叠加战略 / 供应链 / 合规 / 成本四维。"
        ),
        "teaching_notes_internal": (
            "内部锚定中芯国际(688981.SH)公开披露，用于校准设备健康/能耗孪生试点推演；"
            "真实公司名仅在本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-07-29",
        "disclosure_facts": {
            "source": "2025 年年度报告（2026-03-26 披露；证券时报 / 公司公告交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业总收入", "value": "673.23 亿元", "yoy": "+16.49%"},
                {"metric": "归母净利润", "value": "50.41 亿元", "yoy": "+36.29%"},
                {"metric": "扣非归母净利润", "value": "41.24 亿元", "yoy": "+55.9%"},
                {"metric": "销售收入（国际财务报告准则）", "value": "93.27 亿美元", "yoy": "+16.2%（创历史新高）"},
                {"metric": "毛利率（IFRS 口径）", "value": "21.0%", "yoy": "同比 +3.0 个百分点（折旧大幅增长背景下）"},
                {"metric": "年平均产能利用率", "value": "93.5%", "yoy": "同比 +8 个百分点"},
                {"metric": "四季度产能利用率", "value": "95.7%", "yoy": "8 英寸超满载、12 英寸接近满载"},
                {"metric": "月产能（折合 8 英寸标准逻辑）", "value": "105.9 万片", "yoy": "较上年末 +11.1 万片"},
                {"metric": "全年出货总量", "value": "约 970 万片", "yoy": "—"},
                {"metric": "资本开支", "value": "81.0 亿美元", "yoy": "高于年初预期（客户需求强劲 + 设备交付时间延长）"},
                {"metric": "研发投入", "value": "55.19 亿元", "yoy": "占销售收入 8.2%"},
                {"metric": "晶圆收入应用结构", "value": "消费电子 43.2% / 智能手机 23.1% / 工业与汽车 11.0%", "yoy": "—"},
                {"metric": "工业与汽车晶圆收入", "value": "同比增长超六成", "yoy": "汽车产业链加速切换"},
                {"metric": "消费电子晶圆收入", "value": "同比增长超三成", "yoy": "消费政策带动 + 出口增长"},
                {"metric": "中国区收入占比", "value": "85%", "yoy": "产业链在地化切换贯穿全年"},
                {"metric": "晶圆收入尺寸结构", "value": "12 英寸 77% / 8 英寸 23%", "yoy": "—"},
                {"metric": "行业地位", "value": "全球纯晶圆代工第二；中国大陆集成电路制造业领导者", "yoy": "—"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "equipment",
                "claim": "产能利用率高位运行使设备近乎零冗余，非计划停机边际代价被显著放大——设备健康预测维护是该产能结构下 ROI 最直接的数字化场景。",
                "rationale": "年平均产能利用率 93.5%（同比 +8 个百分点），四季度 95.7% 且 8 英寸超满载；满载状态下每小时停机都是直接产出损失，预测维护价值随利用率非线性上升。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["93.5%", "95.7%", "同比 +8 个百分点"],
            },
            {
                "dimension": "equipment",
                "claim": "巨额资本开支叠加设备交付周期延长，存量设备寿命管理与备件前置采购价值上升——新产能补充受外部约束，既有设备 uptime 就是产出天花板。",
                "rationale": "资本开支 81.0 亿美元且高于年初预期，部分原因即设备交付时间延长；交付不确定环境下，让在役设备多跑一小时的价值高于常态。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["81.0 亿美元", "设备交付时间延长"],
            },
            {
                "dimension": "energy",
                "claim": "百万片级月产能规模下，单片能耗的微小优化即放大为显著成本项；能耗孪生（产线级实时能耗镜像 + 碳强度）是毛利率承压期的可控降本杠杆。",
                "rationale": "月产能 105.9 万片、全年出货约 970 万片；晶圆制造是高能耗行业，规模效应使 kWh/片 的优化直接进入毛利率（21.0%）敏感区间。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["105.9 万片", "约 970 万片", "21.0%"],
            },
            {
                "dimension": "strategy",
                "claim": "净利增速显著高于营收增速，经营杠杆主要来自利用率提升——'效率驱动盈利'结构使设备综合效率(OEE)类指标上升为一级经营指标。",
                "rationale": "归母净利 +36.29% 远超营收 +16.49%，公司自述业绩驱动因素为晶圆销售量增加与产能利用率上升（93.5%）；效率指标与盈利的传导链条清晰。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["+36.29%", "+16.49%", "93.5%"],
            },
            {
                "dimension": "cost",
                "claim": "毛利率在折旧大幅增长背景下逆势提升，说明折旧是最大成本压力源——设备资产利用最大化（健康度维持 + 停机减少）是对冲折旧压力的直接手段。",
                "rationale": "毛利率 21.0%、同比 +3.0 个百分点，且明确标注'折旧大幅增长背景下'；重资产模式中折旧刚性，唯有产出爬坡与设备可用率能摊薄。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["21.0%", "同比 +3.0 个百分点"],
            },
            {
                "dimension": "compliance",
                "claim": "产业链在地化与外部设备供应不确定性并存，设备生命周期延长策略与供应合规管理将长期并行。",
                "rationale": "中国区收入占比 85%、在地化切换贯穿全年；同时设备交付时间延长暴露外部供应不确定性，既有设备的健康管理兼具经营与合规韧性双重意义。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["85%"],
            },
        ],
    },
    {
        # 🌍 全球化锚 ①：晶圆代工全球标杆（2026-08-03 杜总定调「第一批必须全球化」）
        # 与 case_semicon_2026（国内制造龙头）构成同支柱国际/国内对照组。
        "case_id": "case_semicon_foundry_global_2026",
        "subject_anon": "某某全球晶圆代工龙头（研究案例·公开披露·全球）",
        "industry": "半导体 / 晶圆代工（全球标杆）",
        "real_anchor": "台积电 TSMC（2330.TW / TSM.NYSE）",  # 🔴 内部锚定，仅 internal 视图
        "scope": "global",
        "value_chain_node": "制造（先进制程产能咽喉）",
        "recommended_interfaces": [
            "industry_research",
            "executive_cockpit",
            "supply_chain",
            "cost_analysis",
            "compliance_q",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」在全球晶圆代工标杆上的产业级推演："
            "先进制程结构 → 定价权 → 毛利率传导链，为国内同支柱企业提供标杆差距对照基线。"
        ),
        "teaching_notes_internal": (
            "内部锚定台积电(2330.TW)公开年报，用于建立「制造支柱」国际标杆基线，"
            "与中芯国际案例形成国际/国内同支柱对照；真名仅本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-08-03",
        "disclosure_facts": {
            "source": "2025 年度年报及 2025Q4 财报新闻稿（2026-01-15 发布；公司投资人关系官网年报页交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业收入净额", "value": "新台币 38,090.5 亿元", "yoy": "+32%"},
                {"metric": "营业收入（美元口径）", "value": "1,222.4 亿美元", "yoy": "+35.6%"},
                {"metric": "归属母公司净利", "value": "新台币 17,178.8 亿元", "yoy": "+46%"},
                {"metric": "营业毛利", "value": "新台币 22,812.9 亿元", "yoy": "+40%"},
                {"metric": "全年毛利率", "value": "59.9%", "yoy": "较上年提升（营收增速 32% 显著高于成本增速 20%）"},
                {"metric": "营业净利", "value": "新台币 19,360.9 亿元", "yoy": "+46%"},
                {"metric": "净利率（美元口径）", "value": "45.1%", "yoy": "净利同比 +50.9%"},
                {"metric": "四季度营收", "value": "33.73 亿美元级单季 337.3 亿美元", "yoy": "+25.5%（美元口径）"},
                {"metric": "四季度毛利率 / 营业利益率 / 净利率", "value": "62.3% / 54.0% / 48.3%", "yoy": "单季毛利率高于全年 59.9%"},
                {"metric": "四季度制程结构（占晶圆营收）", "value": "3nm 28% / 5nm 35% / 7nm 14%", "yoy": "—"},
                {"metric": "先进制程占比（7nm 及以下）", "value": "77%", "yoy": "四季度晶圆营收口径"},
                {"metric": "资本支出", "value": "411.6 亿美元", "yoy": "占营收 33.7%"},
                {"metric": "经营活动现金流 / 自由现金流", "value": "754.2 亿美元 / 345.9 亿美元", "yoy": "—"},
                {"metric": "净资产收益率 ROE", "value": "36.4%", "yoy": "资产回报率 ROA 24.2%"},
                {"metric": "2026Q1 营收指引", "value": "346 亿 ~ 358 亿美元", "yoy": "公司管理层公开指引"},
                {"metric": "全球产能布局", "value": "本土先进制程基地 + 日本熊本合资厂 + 美国厂 + 中国大陆 8 英寸厂", "yoy": "年报披露的多地制造网络"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "先进制程占比与毛利率高度同向——技术代差即定价权，制程领先度是毛利率的一阶决定变量，而非规模。",
                "rationale": "7nm 及以下先进制程占四季度晶圆营收 77%（3nm 28% + 5nm 35% + 7nm 14%），同期全年毛利率 59.9%、四季度 62.3%；同业成熟制程厂商毛利率普遍在 20% 量级，差距主要来自制程结构而非产能规模。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["77%", "59.9%", "62.3%", "3nm 28%"],
            },
            {
                "dimension": "cost",
                "claim": "资本支出占营收三分之一形成刚性折旧前置，产能爬坡速度成为单位成本的决定性变量——重资产模式下时间就是成本。",
                "rationale": "2025 年资本支出 411.6 亿美元，占营收 33.7%；折旧随产能落地即刻计入，唯有产出快速爬坡可摊薄。经营现金流 754.2 亿美元支撑了这一强度而未损伤自由现金流（345.9 亿美元）。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["411.6 亿美元", "33.7%", "345.9 亿美元"],
            },
            {
                "dimension": "supply_chain",
                "claim": "制造网络由单一区域集中转向多地分散，地缘驱动的产能布局将长期抬升单位制造成本与协同复杂度。",
                "rationale": "年报披露产能已覆盖本土先进制程基地、日本合资厂、美国厂与中国大陆 8 英寸厂；海外新厂在人力、供应链配套与爬坡效率上通常弱于本土成熟基地，属于以成本换韧性的战略选择。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["多地制造网络"],
            },
            {
                "dimension": "cost",
                "claim": "单季毛利率高于全年均值，说明盈利弹性主要来自产能利用与良率爬坡的季度节奏，而非价格谈判。",
                "rationale": "四季度毛利率 62.3% 高于全年 59.9%，营业利益率 54.0%；在制程结构季度内基本稳定的前提下，差额主要由稼动率与良率爬坡贡献。",
                "assertion_type": "descriptive",
                "value_judgment": "medium",
                "key_figures": ["62.3%", "59.9%", "54.0%"],
            },
            {
                "dimension": "strategy",
                "claim": "管理层对下一季度给出环比继续增长的指引，指向先进制程需求在 AI 驱动下延续，产能紧张短期难缓解。",
                "rationale": "2026Q1 营收指引 346 亿 ~ 358 亿美元，高于 2025Q4 的 337.3 亿美元；公司自述受益于先进制程需求强劲。对下游客户意味着先进产能仍需提前锁定。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["346 亿 ~ 358 亿美元", "337.3 亿美元"],
            },
            {
                "dimension": "compliance",
                "claim": "先进制程产能高度集中于少数节点与少数基地，使其成为全球供应链的单点风险，也是各国产业政策的首要干预对象。",
                "rationale": "先进制程占比 77% 且主要产能集中于有限基地；多地建厂本身即为对政策与地缘风险的响应。对国内企业而言，该结构决定了先进制程可获得性属外部约束变量而非采购变量。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["77%"],
            },
        ],
    },
    {
        # 🌍 全球化锚 ②：光刻设备全球卡点（2026-08-03）
        # 决定所有晶圆制造企业（含国内锚）先进制程天花板的上游控制点。
        "case_id": "case_semicon_litho_global_2026",
        "subject_anon": "某某全球光刻设备公司（研究案例·公开披露·全球）",
        "industry": "半导体 / 光刻设备（全球卡点）",
        "real_anchor": "阿斯麦 ASML（ASML.AS / ASML.NASDAQ）",  # 🔴 内部锚定，仅 internal 视图
        "scope": "global",
        "value_chain_node": "设备（先进制程准入卡点）",
        "recommended_interfaces": [
            "industry_research",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "bid_intel",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」在全球光刻设备卡点企业上的产业级推演："
            "其订单结构与区域收入结构，是判断全球晶圆产能扩张节奏与设备可得性的领先指标。"
        ),
        "teaching_notes_internal": (
            "内部锚定阿斯麦(ASML.AS)公开年报，用于建立「设备支柱」国际基线；"
            "该锚是国内制造锚（中芯国际）先进制程天花板的上游解释变量。真名仅本视图出现。"
        ),
        "status": "active",
        "updated_at": "2026-08-03",
        "disclosure_facts": {
            "source": "2025 年第四季度及全年财报（2026-01-28 公司官网新闻稿发布；财经媒体交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "全年净销售额", "value": "326.67 亿欧元", "yoy": "+15.6%（上年 282.63 亿欧元）"},
                {"metric": "全年净利润", "value": "96.09 亿欧元", "yoy": "+26.9%（上年 75.72 亿欧元）"},
                {"metric": "全年毛利率", "value": "52.8%", "yoy": "同比 +1.5 个百分点（上年 51.3%）"},
                {"metric": "每股收益（基本）", "value": "24.73 欧元", "yoy": "上年 19.25 欧元"},
                {"metric": "四季度净销售额", "value": "97.18 亿欧元", "yoy": "创单季历史纪录"},
                {"metric": "四季度净利润 / 毛利率", "value": "28.40 亿欧元 / 52.2%", "yoy": "—"},
                {"metric": "四季度新增订单", "value": "131.58 亿欧元", "yoy": "其中 EUV 订单 74 亿欧元，创纪录"},
                {"metric": "全年新增订单", "value": "280.35 亿欧元", "yoy": "上年 188.99 亿欧元"},
                {"metric": "年末在手订单（backlog）", "value": "388.0 亿欧元", "yoy": "三季度末为 359.4 亿欧元"},
                {"metric": "装机基础管理销售（服务与现场选件）", "value": "81.93 亿欧元", "yoy": "+26.2%（上年 64.94 亿欧元）"},
                {"metric": "新光刻系统销售台数", "value": "300 台", "yoy": "上年 380 台（台数下降而营收增长）"},
                {"metric": "二手光刻系统销售台数", "value": "27 台", "yoy": "上年 38 台"},
                {"metric": "产品收入结构（美元口径）", "value": "EUV 35.5% / ArF 浸没式 31.6% / 服务与现场选件 25.1% / KrF 3.1% / 量测检测 2.5%", "yoy": "—"},
                {"metric": "High-NA 进展", "value": "四季度确认两台 High-NA 系统收入", "yoy": "下一代节点设备进入商业化确认阶段"},
                {"metric": "2026 全年指引", "value": "净销售额 340 亿 ~ 390 亿欧元，毛利率 51% ~ 53%", "yoy": "高于市场普遍预期区间"},
                {"metric": "中国大陆收入占比（2026 预期）", "value": "约 20%", "yoy": "与在手订单中的中国占比基本一致"},
                {"metric": "股票回购计划", "value": "最高 120 亿欧元，2028-12-31 前执行完毕", "yoy": "新计划"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "系统出货台数下降而营收显著增长，证明价值中心已从台数转向单机价值——设备行业的增长引擎是技术代际升级，不是产能堆量。",
                "rationale": "新光刻系统销售 300 台，较上年 380 台减少约 21%，同期净销售额仍增长 15.6% 至 326.67 亿欧元；EUV 占收入 35.5% 且四季度 EUV 订单达 74 亿欧元，结构升级抵消了台数下滑。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["300 台", "380 台", "+15.6%", "35.5%"],
            },
            {
                "dimension": "supply_chain",
                "claim": "在手订单已超过全年营收规模，使该企业的订单簿成为全球晶圆产能扩张节奏的领先指标——它比任何晶圆厂的公告都提前反映真实扩产意图。",
                "rationale": "年末在手订单 388.0 亿欧元，高于全年净销售额 326.67 亿欧元，覆盖倍数约 1.19 倍；四季度单季新增订单 131.58 亿欧元创纪录。设备订单通常领先产能落地 12~24 个月。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["388.0 亿欧元", "326.67 亿欧元", "131.58 亿欧元"],
            },
            {
                "dimension": "strategy",
                "claim": "创纪录订单集中于 EUV，确认 AI 算力资本开支已完成向上游设备端的传导，先进制程扩产周期进入加速段。",
                "rationale": "四季度新增订单 131.58 亿欧元中 EUV 占 74 亿欧元（约 56%）；公司自述客户基于 AI 需求可持续性上调中期产能计划，逻辑与存储客户同步加速。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["74 亿欧元", "131.58 亿欧元"],
            },
            {
                "dimension": "cost",
                "claim": "服务与装机基础收入占比已达四分之一且增速高于整体，形成年金化收入垫——这是设备商穿越资本开支周期的结构性缓冲。",
                "rationale": "装机基础管理销售 81.93 亿欧元，同比 +26.2%，高于整体营收增速 15.6%，占美元口径收入 25.1%；该部分与存量装机量挂钩，受新机订单波动影响较小。",
                "assertion_type": "descriptive",
                "value_judgment": "medium",
                "key_figures": ["81.93 亿欧元", "+26.2%", "25.1%"],
            },
            {
                "dimension": "compliance",
                "claim": "中国大陆收入占比回落至约两成且与在手订单结构一致，说明区域收入结构已由出口管制政策而非市场需求决定。",
                "rationale": "公司公开指引 2026 年中国大陆营收占比约 20%，并明确该比例与当前在手订单中的中国占比基本一致——占比由可交付范围决定，属政策变量而非商务变量。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["约 20%"],
            },
            {
                "dimension": "equipment",
                "claim": "High-NA 首批系统完成收入确认，标志下一代节点的设备准入门槛开始形成——先进制程的代际差距将由设备可得性直接锁定。",
                "rationale": "四季度确认两台 High-NA 系统收入，是该技术从研发验证转入商业交付的分界点；对无法获得该类设备的制造企业，节点推进将转为依赖多重曝光等成本更高的替代路径。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["两台 High-NA"],
            },
        ],
    },
    {
        "case_id": "case_3c_2026",
        "subject_anon": "某某精密制造公司（研究案例·公开披露）",
        "industry": "消费电子 / 3C 精密制造",
        "real_anchor": "立讯精密（002475.SZ）",  # 🔴 内部锚定真实上市公司，仅 internal 视图
        "recommended_interfaces": [
            "industry_research",
            "pm_maintenance",
            "energy_carbon",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "cost_analysis",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」在 3C 精密制造标杆企业上推演 "
            "消费电子 / 汽车电子 / 通讯数据中心三大业务板块的战略、供应链、合规与成本四维，"
            "并叠加设备健康 / 能耗孪生视角。"
        ),
        "teaching_notes_internal": (
            "内部锚定立讯精密(002475.SZ)公开披露，用于校准 3C 精密制造行业研究推演；"
            "真实公司名仅在本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-07-31",
        "disclosure_facts": {
            "source": "2025 年年度报告（2026-04 披露；公司官网 / 巨潮资讯 / 证券日报交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业总收入", "value": "3323.44 亿元", "yoy": "+23.64%"},
                {"metric": "归母净利润", "value": "166.00 亿元", "yoy": "+24.20%"},
                {"metric": "扣除非经常性损益净利润", "value": "146.90 亿元", "yoy": "+19.44%"},
                {"metric": "综合毛利率", "value": "11.91%", "yoy": "同比 +1.5 个百分点"},
                {"metric": "消费电子营收", "value": "2642.66 亿元", "yoy": "+13.37%", "share": "79.52%"},
                {"metric": "汽车电子营收", "value": "392.55 亿元", "yoy": "+185.34%（爆发式增长，第二引擎成型）", "share": "11.81%"},
                {"metric": "通讯及数据中心营收", "value": "245.68 亿元", "yoy": "+33.81%", "share": "7.39%"},
                {"metric": "海外营收占比", "value": "约 78%", "yoy": "海外基地近 30 国、100+ 制造据点"},
                {"metric": "前五大客户销售占比", "value": "约 78%", "yoy": "客户集中度偏高（消费电子代工特征）"},
                {"metric": "研发支出", "value": "约 110 亿元", "yoy": "占营收约 3.3%（持续高投入）"},
                {"metric": "经营活动现金流净额", "value": "约 340 亿元", "yoy": "同比显著改善"},
                {"metric": "资产负债率", "value": "约 62%", "yoy": "重资产扩张期可控区间"},
                {"metric": "全球地位", "value": "全球消费电子精密制造龙头；AirPods 主力代工、Watch/手机整机与零件核心供应商", "yoy": "—"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "汽车电子营收同比 +185% 已成第二增长引擎，业务结构从单一消费电子代工转向'消费电子基本盘 + 汽车电子新引擎'双轮。",
                "rationale": "汽车电子 392.55 亿、占比 11.81%、同比 +185.34%；通讯及数据中心 +33.81% 为第三增长极；与'三个五年'全球化多品类战略自洽，降低对单一客户的周期依赖。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["+185.34%", "11.81%", "+33.81%"],
            },
            {
                "dimension": "supply_chain",
                "claim": "前五大客户占比约 78% 凸显客户集中风险，海外基地近 30 国 100+ 据点构成地缘韧性，同时放大全球供应链协同与库存优化需求。",
                "rationale": "消费电子代工天然客户集中；海外营收约 78%、制造据点遍布近 30 国，使其供应链调度跨多时区多关境，对实时产能/物流/关税协同的智能体需求强。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["约 78%", "近 30 国", "100+ 据点"],
            },
            {
                "dimension": "compliance",
                "claim": "海外营收约 78% 使全球贸易合规、出口管制、ESG 碳足迹披露成为持续性核心风险面。",
                "rationale": "海外基地近 30 国、100+ 据点；多关境制造使出口管制、原产地规则、碳边境调节机制(CBAM)合规贯穿经营，合规智能体价值突出。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["约 78%"],
            },
            {
                "dimension": "cost",
                "claim": "综合毛利率仅 11.91% 属代工薄利结构，成本改善空间在汽车电子高毛利品类占比提升与制造自动化降本，而非简单压价。",
                "rationale": "毛利率 11.91%（同比 +1.5pct）仍处制造业低位；汽车电子毛利率显著高于消费电子，其占比上升是毛利率结构性改善主因；设备自动化(OEE)提升是直接降本杠杆。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["11.91%", "+1.5pct", "+185.34%"],
            },
            {
                "dimension": "equipment",
                "claim": "3C 精密制造以 SMT 贴片 / CNC 加工 / 注塑成型 / 自动化装配为主，设备数量庞大、单台价值相对半导体低，但停机对整线节拍影响直接——集群化健康管理 ROI 高。",
                "rationale": "消费电子整机组装产线设备以万计；SMT 贴片机、CNC、注塑机、点胶/锁附/检测自动化设备的节拍耦合紧密，单点停线即整线停滞，预测维护按集群而非单台核算价值更优。",
                "assertion_type": "descriptive",
                "value_judgment": "medium",
                "key_figures": ["以万计", "集群化"],
            },
        ],
    },
    {
        "case_id": "case_newenergy_2026",
        "subject_anon": "某某新能源公司（研究案例·公开披露）",
        "industry": "新能源 / 动力电池与储能",
        "real_anchor": "宁德时代（300750.SZ）",  # 🔴 内部锚定真实上市公司，仅 internal 视图
        "recommended_interfaces": [
            "industry_research",
            "pm_maintenance",
            "energy_carbon",
            "executive_cockpit",
            "supply_chain",
            "compliance_q",
            "cost_analysis",
        ],
        "teaching_notes_anon": (
            "对外以匿名案例呈现，演示「研究案例范式」在新能源动力电池标杆企业上推演 "
            "动力电池 / 储能双板块的战略、供应链(锂价/材料)、合规(电池碳足迹/海外)与成本四维，"
            "并叠加电芯产线设备健康 / 能耗孪生视角。"
        ),
        "teaching_notes_internal": (
            "内部锚定宁德时代(300750.SZ)公开披露，用于校准新能源动力电池行业研究推演；"
            "真实公司名仅在本视图出现，对外一律匿名。"
        ),
        "status": "active",
        "updated_at": "2026-07-31",
        "disclosure_facts": {
            "source": "2025 年年度报告（2026-03 披露；公司官网 / 巨潮资讯 / 上海证券报交叉核对）",
            "fiscal_year": 2025,
            "facts": [
                {"metric": "营业总收入", "value": "4237 亿元", "yoy": "+17%"},
                {"metric": "归母净利润", "value": "722 亿元", "yoy": "+42%"},
                {"metric": "综合毛利率", "value": "26.27%", "yoy": "显著高于代工制造业，技术溢价体现"},
                {"metric": "动力电池系统营收", "value": "1921.25 亿元", "yoy": "—", "share": "69.38%"},
                {"metric": "储能电池系统营收", "value": "532.61 亿元", "yoy": "系统集出货同比 +160%", "share": "19.23%"},
                {"metric": "锂电池销量", "value": "661 GWh", "yoy": "同比 +39%"},
                {"metric": "全球动力电池市占率", "value": "39.2%", "yoy": "连续九年全球第一"},
                {"metric": "全球储能电池市占率", "value": "30.4%", "yoy": "全球第一"},
                {"metric": "研发费用", "value": "约 221 亿元", "yoy": "占营收约 5.2%"},
                {"metric": "产能利用率", "value": "高位运行", "yoy": "供需紧平衡、产能爬坡持续"},
                {"metric": "海外营收占比", "value": "约 30%+", "yoy": "欧洲/北美/东南亚基地布局加速"},
                {"metric": "全球地位", "value": "全球动力电池与储能双料龙头；麒麟/神行/钠新等新技术量产领先", "yoy": "—"},
            ],
        },
        "derived_insights": [
            {
                "dimension": "strategy",
                "claim": "储能电池系统营收同比 +160% 已成第二爆发极，业务结构从动力电池单核转向'动力基本盘 + 储能增长极'双核。",
                "rationale": "储能 532.61 亿、占比 19.23%、系统集出货 +160%；全球储能市占 30.4% 第一；与全球能源转型及电网侧储能需求自洽，对冲动力电池周期波动。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["+160%", "19.23%", "30.4%"],
            },
            {
                "dimension": "supply_chain",
                "claim": "锂盐及关键材料价格周期直接影响成本，向上游锂资源/材料一体化与回收闭环延伸是供应链韧性核心。",
                "rationale": "动力电池成本结构中锂盐占比高且价格波动大；年报强调一体化与回收（锂回收率行业领先），供应链智能体需在锂价波动下做采购节奏与库存策略推演。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["锂价周期", "回收闭环"],
            },
            {
                "dimension": "compliance",
                "claim": "电池全生命周期碳足迹与海外建厂(欧洲/北美)使电池护照、碳披露、跨境合规成为持续性风险面。",
                "rationale": "海外营收约 30%+、海外基地加速；欧盟电池法规(碳足迹/电池护照)、CBAM 等使合规从'出口文件'升级为'产品准入门槛'，合规智能体价值突出。",
                "assertion_type": "predictive",
                "value_judgment": "high",
                "key_figures": ["约 30%+", "电池护照", "碳足迹"],
            },
            {
                "dimension": "cost",
                "claim": "综合毛利率 26.27% 远高于代工制造业，技术溢价 + 规模效应构筑成本护城河；成本改善方向在良率提升与能耗优化而非压供应商。",
                "rationale": "毛利率 26.27% 体现技术溢价；661GWh 规模效应摊薄固定成本；电芯制造高能耗，单 Wh 能耗优化直接进入毛利敏感区间，能耗孪生价值高。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["26.27%", "661 GWh"],
            },
            {
                "dimension": "equipment",
                "claim": "电芯产线以涂布 / 辊压 / 卷绕(叠片) / 化成分容为核心，化成分容工序能耗占整线 30%+ 且设备数量巨大——化成分容设备的能耗孪生与预测维护 ROI 最直接。",
                "rationale": "化成分容是电芯产线能耗最高、设备最多的工序（单 GWh 对应数百台分容柜）；涂布机幅宽/速度决定产能节拍；该工序设备健康与能耗直接决定整线 OEE 与单位 kWh 成本。",
                "assertion_type": "descriptive",
                "value_judgment": "high",
                "key_figures": ["30%+", "数百台分容柜", "OEE"],
            },
        ],
    },
]


class CaseCuratorAgent(BaseAgent):
    """案例库策展 Agent"""

    name = "case_curator"
    description = "案例库策展：列/汇总案例、挂推荐接口、生成教学双版(对外匿名/对内真名)"

    def __init__(self):
        self.store_path = CASE_STORE_PATH

    def _load(self) -> list:
        try:
            if os.path.exists(self.store_path):
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save(self, cases: list):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False, indent=2)

    def _ensure_seed(self):
        """案例库为空时写入种子；已有存量时按 case_id 增量补齐缺失的默认案例（升级路径）。"""
        cases = self._load()
        if not cases:
            self._save(DEFAULT_CASES)
            return
        # 升级路径：生产存量 cases.json 可能只含旧案例，补齐新增默认案例
        known = {c.get("case_id") for c in cases}
        missing = [c for c in DEFAULT_CASES if c["case_id"] not in known]
        if missing:
            self._save(cases + missing)

    async def analyze(self, goal: str) -> dict:
        self._ensure_seed()
        g = goal.lower()
        # 🔴 多案例：若 goal 明确带 case_id，直接返回该案例详情
        import re

        m = re.search(r"case_[a-z0-9_]+", goal)
        if m:
            c = self._get_case(m.group(0))
            if c:
                return self._case_detail(c)
        # 搜索 / 查找（按 case_id / 匿名主题 / 行业 / 教学笔记模糊匹配）
        if "搜索" in goal or "search" in g or "查找" in goal or "查询" in goal or "找" in goal:
            return self._search_cases(goal)
        if "教学" in goal or "双版" in goal or "teaching" in g:
            return self._teaching_dual_version()
        if "推荐接口" in goal or "recommended" in g or "接口" in goal:
            return self._recommended_interfaces()
        # 默认：列出 / 汇总案例库
        return self._list_cases()

    # ---------- 多案例能力（#398） ----------

    def _get_case(self, case_id: str) -> dict | None:
        for c in self._load():
            if c["case_id"] == case_id:
                return c
        return None

    def _active_case_id(self) -> str | None:
        """默认案例：第一个 active 案例（先有后优，单案例时即它）。"""
        for c in self._load():
            if c.get("status", "active") == "active":
                return c["case_id"]
        cases = self._load()
        return cases[0]["case_id"] if cases else None

    def _search_cases(self, query: str) -> dict:
        import re

        q = query.lower().replace("搜索", "").replace("查找", "").replace("查询", "").replace("找", "").strip()
        if not q:
            return self._list_cases()
        # 分词：英文/数字连续段整体保留；中文按 2 字滑动窗口生成词素，任一命中即匹配
        raw_tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", q)
        tokens: list[str] = []
        for t in raw_tokens:
            if re.search(r"[A-Za-z0-9]", t):
                if len(t) >= 2:
                    tokens.append(t)
            else:
                for i in range(len(t) - 1):
                    tokens.append(t[i : i + 2])
        if not tokens:
            tokens = [q]
        out = []
        for c in self._load():
            hay = " ".join([
                c.get("case_id", ""), c.get("subject_anon", ""),
                c.get("industry", ""), c.get("real_anchor", ""),
                c.get("teaching_notes_anon", ""),
            ]).lower()
            if any(t.lower() in hay for t in tokens):
                out.append(c)
        return {
            "status": "completed",
            "query": q,
            "tokens": tokens,
            "match_count": len(out),
            "cases": [
                {
                    "case_id": c["case_id"],
                    "subject_anon": c["subject_anon"],
                    "industry": c["industry"],
                    "status": c.get("status", "active"),
                }
                for c in out
            ],
            "summary": f"搜索「{q}」命中 {len(out)} 个案例" if out else f"搜索「{q}」无匹配案例",
        }

    def _case_detail(self, c: dict) -> dict:
        """单案例详情（对外匿名视图，绝不带 real_anchor）。

        加强版（2026-08-02）：放行 disclosure_facts + derived_insights，
        让前端抽屉直接渲染公开披露事实表与多维推演结论。
        这两个字段本身不含 real_anchor，配合 /cases/my 双保险已在生产验证合规。
        """
        return {
            "status": "completed",
            "case": {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "recommended_interfaces": c.get("recommended_interfaces", []),
                "teaching_notes_anon": c.get("teaching_notes_anon", ""),
                "pilot_scenario": c.get("pilot_scenario"),  # 匿名安全：仅场景描述，无真名
                "status": c.get("status", "active"),
                "updated_at": c.get("updated_at", ""),
                # 加强版：放行事实+结论（无真名）
                "disclosure_facts": c.get("disclosure_facts", {}),
                "derived_insights": c.get("derived_insights", []),
                # 全球化锚标识（2026-08-03）：匿名安全
                "scope": c.get("scope", "domestic"),
                "value_chain_node": c.get("value_chain_node", ""),
            },
            "summary": f"案例 {c['case_id']} 详情（{c['subject_anon']}）",
        }

    def _list_cases(self) -> dict:
        cases = self._load()
        return {
            "status": "completed",
            "case_count": len(cases),
            "active_case_id": self._active_case_id(),
            "cases": [
                {
                    "case_id": c["case_id"],
                    "subject_anon": c["subject_anon"],
                    "industry": c["industry"],
                    "status": c.get("status", "active"),
                    "updated_at": c.get("updated_at", ""),
                    # 加强版（2026-08-02）：卡片角标用，零成本算出
                    "fact_count": len(c.get("disclosure_facts", {}).get("facts", []) or []),
                    "insight_count": len(c.get("derived_insights", []) or []),
                    # 全球化锚标识（2026-08-03）：匿名安全，仅范围与价值链节点，无真名
                    "scope": c.get("scope", "domestic"),
                    "value_chain_node": c.get("value_chain_node", ""),
                }
                for c in cases
            ],
            "summary": f"案例库共 {len(cases)} 个研究案例（均对外匿名）",
        }

    def _recommended_interfaces(self) -> dict:
        cases = self._load()
        out = [
            {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "recommended_interfaces": c.get("recommended_interfaces", []),
            }
            for c in cases
        ]
        return {
            "status": "completed",
            "cases": out,
            "summary": f"已为 {len(cases)} 个案例挂载推荐接口",
        }

    def _teaching_dual_version(self) -> dict:
        """生成教学双版：对外匿名 / 对内真名（real_anchor 不进 external 视图）。"""
        cases = self._load()
        dual = []
        for c in cases:
            external = {
                "case_id": c["case_id"],
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "teaching_notes": c.get("teaching_notes_anon", ""),
            }
            internal = {
                "case_id": c["case_id"],
                "real_anchor": c.get("real_anchor"),  # 🔴 仅内部视图含真名
                "subject_anon": c["subject_anon"],
                "industry": c["industry"],
                "teaching_notes": c.get("teaching_notes_internal", ""),
            }
            dual.append({"teaching_external": external, "teaching_internal": internal})
        return {
            "status": "completed",
            "dual_version_count": len(dual),
            "dual_versions": dual,
            "summary": f"生成 {len(dual)} 个案例的教学双版（外部匿名 / 内部真名）",
        }


case_curator_agent = CaseCuratorAgent()
