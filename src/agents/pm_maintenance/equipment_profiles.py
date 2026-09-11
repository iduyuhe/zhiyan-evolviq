# 多行业典型设备配置模板（设备类型图谱）

"""多行业典型设备类型定义（半导体 / 3C 精密制造 / 新能源动力电池）。

每类设备包含：
- 基本信息（类型、典型型号、供应商）
- OPC-UA 默认标签映射（用于网关接入）
- 关键部件与典型寿命
- 能耗特征（功率范围）
- 健康分计算参考

用于"先建模板、客户设备按型号匹配接入"策略：
客户入驻时选行业 → list_by_industry() 拉出该行业全部设备模板 →
按型号匹配（同型号直接套模板，异型号按模板规则快速适配）。
"""

from dataclasses import dataclass, field
from typing import List, Dict

# ── 设备分类 ──────────────────────────────────────────────────────
# 根据全球纯晶圆代工第二的匿名企业（内部锚定中芯国际·Fab8 28nm）
# 实际产线部署的主流设备型号整理。

EQUIPMENT_CATEGORIES = {
    "lithography": {
        "cn_name": "光刻机",
        "description": "晶圆光刻曝光——Fab 核心瓶颈设备",
        "vendors": ["ASML", "Nikon", "Canon"],
    },
    "etch": {
        "cn_name": "刻蚀机",
        "description": "介电质/金属刻蚀——各向异性加工",
        "vendors": ["AMEC 中微", "Lam Research", "Applied Materials", "Tokyo Electron"],
    },
    "deposition": {
        "cn_name": "薄膜沉积",
        "description": "PVD/CVD/PECVD/ALD——薄膜生长",
        "vendors": ["Applied Materials", "Lam Research", "Tokyo Electron"],
    },
    "cmp": {
        "cn_name": "化学机械抛光",
        "description": "晶圆平坦化——CMP 工艺",
        "vendors": ["Applied Materials", "Ebara"],
    },
    "inspection": {
        "cn_name": "检测/量测",
        "description": "晶圆缺陷检测、膜厚量测、CD-SEM",
        "vendors": ["KLA", "AMAT", "Hitachi High-Tech"],
    },
    "implant": {
        "cn_name": "离子注入",
        "description": "掺杂工艺（阱/源漏注入）",
        "vendors": ["Applied Materials", "Axcelis"],
    },
    # ── 3C 精密制造（2026-07-31 设备库扩列）──
    "smt": {
        "cn_name": "SMT 贴片机",
        "description": "表面贴装——PCB 元器件高速贴装，产线节拍核心",
        "vendors": ["FUJI", "ASMPT", "Panasonic", "Yamaha"],
    },
    "cnc": {
        "cn_name": "CNC 加工中心",
        "description": "金属/非金属精密结构件铣削加工",
        "vendors": ["FANUC", "Brother", "DMG MORI", "Haas"],
    },
    "injection": {
        "cn_name": "注塑机",
        "description": "塑料精密结构件成型（外壳/支架）",
        "vendors": ["Haitian", "Engel", "ARBURG", "Sumitomo"],
    },
    # ── 新能源 动力电池（2026-07-31 设备库扩列）──
    "coating": {
        "cn_name": "涂布机",
        "description": "锂电电芯极片涂布——幅宽/面密度决定产能节拍",
        "vendors": ["PNT", "CKD", "先导智能", "赢合科技"],
    },
    "winding": {
        "cn_name": "卷绕/叠片机",
        "description": "电芯卷绕或叠片成型——决定电芯一致性与良率",
        "vendors": ["先导智能", "赢合科技", "GL Automation"],
    },
    "formation": {
        "cn_name": "化成分容柜",
        "description": "电芯化成/分容/老化——产线能耗最高、设备数量最大工序",
        "vendors": ["瑞能", "杭可科技", "先导智能"],
    },
    # ── 造船 / 船舶总装制造（2026-09-11 扩列，沪东造船试点）──
    "drydock": {
        "cn_name": "船坞",
        "description": "船舶总装/下水核心设施——承载巨型总段与举力作业",
        "vendors": ["船厂自建（非标）", "中交船舶"],
    },
    "gantry_crane": {
        "cn_name": "龙门吊",
        "description": "巨型总段吊装、移位与舾装配合——船厂大件物流核心",
        "vendors": ["振华重工", "太原重工", "三一海工"],
    },
    "welding_robot": {
        "cn_name": "焊接机器人",
        "description": "平面/曲面分段自动化焊接——决定焊缝质量与节拍",
        "vendors": ["FANUC", "KUKA", "唐山开元", "瑞凌"],
    },
    "cnc_plate": {
        "cn_name": "数控切割机",
        "description": "钢板数控下料——切割速度与割缝质量决定材料利用率",
        "vendors": ["梅塞尔", "百超", "天田", "华工激光"],
    },
    "blast_paint": {
        "cn_name": "抛丸涂装线",
        "description": "分段除锈+涂装——表面粗糙度与 VOC 合规双约束",
        "vendors": ["非标集成（船厂自建）", "墅研"],
    },
    "marine_engine": {
        "cn_name": "船用柴油机",
        "description": "低速大功率船用主机/轮机——全船动力核心，连续运行",
        "vendors": ["沪东重机", "中船动力", "MAN ES", "Wärtsilä"],
    },
}

# ── 行业归属映射（预设层：客户入驻选行业 → 自动匹配该行业设备模板）──
# key = 行业代码，value = 该行业的设备类型列表
INDUSTRY_EQUIPMENT_TYPES: Dict[str, List[str]] = {
    "semiconductor": ["lithography", "etch", "deposition", "cmp", "inspection", "implant"],
    "3c": ["smt", "cnc", "injection"],
    "new_energy": ["coating", "winding", "formation"],
    "shipbuilding": ["drydock", "gantry_crane", "welding_robot", "cnc_plate", "blast_paint", "marine_engine"],
}

INDUSTRY_LABELS: Dict[str, str] = {
    "semiconductor": "半导体 / 集成电路晶圆制造",
    "3c": "3C 消费电子 / 精密制造",
    "new_energy": "新能源 / 动力电池与储能",
    "shipbuilding": "造船 / 船舶总装制造",
}

# 反向注入：让每个设备类别自带 industry 归属，避免调用方硬编码判断
for _ind, _types in INDUSTRY_EQUIPMENT_TYPES.items():
    for _t in _types:
        if _t in EQUIPMENT_CATEGORIES:
            EQUIPMENT_CATEGORIES[_t]["industry"] = _ind
            EQUIPMENT_CATEGORIES[_t]["industry_cn"] = INDUSTRY_LABELS[_ind]


@dataclass
class EquipmentProfile:
    """单类设备的配置模板"""

    # ── 基础 ──
    equipment_id: str          # e.g. "scanner_1"
    name: str                  # e.g. "ASML NXT:1980Di 光刻机 #1"
    type_cn: str               # e.g. "光刻机"
    vendor: str                # e.g. "ASML"
    model: str                 # e.g. "TWINSCAN NXT:1980Di"

    # ── OPC-UA 标签（网关 simulated → PM 实时健康）────
    # 格式: { tag_name: (default_value, unit, description) }
    opcua_tags: Dict[str, tuple] = field(default_factory=dict)

    # ── 关键部件（名称, [part_no], 典型寿命占比基准）────
    key_parts: List[Dict] = field(default_factory=list)

    # ── 能耗特征（用于 energy_carbon 孪生）────
    power_kw_avg: float = 0    # 典型运行功率（kW）
    power_kw_peak: float = 0   # 峰值功率
    coolant_flow_lpm: float = 0  # 冷却水流速（L/min）

    # ── MTBF 基准（小时）───
    mtbf_hours: int = 2000


# ── 具体设备配置 ──────────────────────────────────────────────────

PROFILES: Dict[str, EquipmentProfile] = {
    "scanner_1": EquipmentProfile(
        equipment_id="scanner_1",
        name="ASML NXT:1980Di 光刻机 #1",
        type_cn="光刻机",
        vendor="ASML",
        model="TWINSCAN NXT:1980Di",
        opcua_tags={
            "ns=2;s=Scanner1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Scanner1.Health": (88.0, "pct", "设备健康分"),
            "ns=2;s=Scanner1.LaserPower": (96.5, "pct", "激光源功率"),
            "ns=2;s=Scanner1.OverlayNm": (2.1, "nm", "套刻精度"),
            "ns=2;s=Scanner1.Vibration": (0.32, "mm/s", "振动"),
            "ns=2;s=Scanner1.ChamberTemp": (22.4, "C", "腔室温度"),
            "ns=2;s=Scanner1.PowerKw": (85.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "激光光源", "part_no": "LGT-4021", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 90},
            {"name": "投影物镜", "part_no": "LNS-8830", "life_remaining_pct": 88, "risk": "low", "replace_lead_days": 120},
            {"name": "掩膜台", "part_no": "MSK-1120", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 45},
            {"name": "晶圆台", "part_no": "WFR-2245", "life_remaining_pct": 91, "risk": "low", "replace_lead_days": 60},
        ],
        power_kw_avg=85.0, power_kw_peak=120.0, coolant_flow_lpm=45.0,
        mtbf_hours=3000,
    ),
    "scanner_2": EquipmentProfile(
        equipment_id="scanner_2",
        name="ASML NXT:1980Di 光刻机 #2",
        type_cn="光刻机",
        vendor="ASML",
        model="TWINSCAN NXT:1980Di",
        opcua_tags={
            "ns=2;s=Scanner2.Status": (True, "bool", "运行状态"),
            "ns=2;s=Scanner2.Health": (79.0, "pct", "设备健康分"),
            "ns=2;s=Scanner2.LaserPower": (82.0, "pct", "激光源功率"),
            "ns=2;s=Scanner2.OverlayNm": (3.5, "nm", "套刻精度"),
            "ns=2;s=Scanner2.Vibration": (0.45, "mm/s", "振动"),
            "ns=2;s=Scanner2.ChamberTemp": (23.8, "C", "腔室温度"),
            "ns=2;s=Scanner2.PowerKw": (88.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "激光光源", "part_no": "LGT-4021", "life_remaining_pct": 45, "risk": "high", "replace_lead_days": 90},
            {"name": "投影物镜", "part_no": "LNS-8830", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 120},
            {"name": "掩膜台", "part_no": "MSK-1120", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 45},
            {"name": "晶圆台", "part_no": "WFR-2245", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 60},
        ],
        power_kw_avg=86.0, power_kw_peak=122.0, coolant_flow_lpm=45.0,
        mtbf_hours=2800,
    ),
    "etcher_1": EquipmentProfile(
        equipment_id="etcher_1",
        name="中微 Primo D-RIE 刻蚀机 #1",
        type_cn="刻蚀机",
        vendor="AMEC 中微",
        model="Primo D-RIE",
        opcua_tags={
            "ns=2;s=Etcher1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Etcher1.Health": (76.2, "pct", "设备健康分"),
            "ns=2;s=Etcher1.ChamberPressure": (45.8, "mtorr", "腔体压力"),
            "ns=2;s=Etcher1.RFPower": (1480.0, "W", "射频功率"),
            "ns=2;s=Etcher1.EtchRate": (312.0, "nm/min", "刻蚀速率"),
            "ns=2;s=Etcher1.EtchRateDev": (3.2, "pct", "刻蚀偏差"),
            "ns=2;s=Etcher1.PowerKw": (42.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "射频电源", "part_no": "RF-3300", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 60},
            {"name": "真空腔体", "part_no": "VAC-7710", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 90},
            {"name": "气体分配盘", "part_no": "GAS-2201", "life_remaining_pct": 45, "risk": "high", "replace_lead_days": 30},
            {"name": "静电卡盘", "part_no": "ESC-5540", "life_remaining_pct": 38, "risk": "high", "replace_lead_days": 45},
        ],
        power_kw_avg=42.0, power_kw_peak=65.0, coolant_flow_lpm=30.0,
        mtbf_hours=2000,
    ),
    "etcher_2": EquipmentProfile(
        equipment_id="etcher_2",
        name="Lam 2300 Kiyo 刻蚀机 #2",
        type_cn="刻蚀机",
        vendor="Lam Research",
        model="2300 Kiyo",
        opcua_tags={
            "ns=2;s=Etcher2.Status": (True, "bool", "运行状态"),
            "ns=2;s=Etcher2.Health": (91.0, "pct", "设备健康分"),
            "ns=2;s=Etcher2.ChamberPressure": (38.2, "mtorr", "腔体压力"),
            "ns=2;s=Etcher2.RFPower": (1650.0, "W", "射频功率"),
            "ns=2;s=Etcher2.EtchRate": (345.0, "nm/min", "刻蚀速率"),
            "ns=2;s=Etcher2.EtchRateDev": (1.8, "pct", "刻蚀偏差"),
            "ns=2;s=Etcher2.PowerKw": (48.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "射频电源", "part_no": "RF-4400", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 60},
            {"name": "真空腔体", "part_no": "VAC-8820", "life_remaining_pct": 90, "risk": "low", "replace_lead_days": 90},
            {"name": "气体分配盘", "part_no": "GAS-3302", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 30},
            {"name": "电极组件", "part_no": "ELC-6610", "life_remaining_pct": 62, "risk": "medium", "replace_lead_days": 45},
        ],
        power_kw_avg=48.0, power_kw_peak=70.0, coolant_flow_lpm=35.0,
        mtbf_hours=2200,
    ),
    "deposition_1": EquipmentProfile(
        equipment_id="deposition_1",
        name="AMAT Endura 薄膜沉积 #1",
        type_cn="薄膜沉积",
        vendor="Applied Materials",
        model="Endura 300mm PVD",
        opcua_tags={
            "ns=2;s=Deposition1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Deposition1.Health": (92.1, "pct", "设备健康分"),
            "ns=2;s=Deposition1.ChamberVacuum": (8e-7, "torr", "腔体真空度"),
            "ns=2;s=Deposition1.HeaterTemp": (385.0, "C", "加热器温度"),
            "ns=2;s=Deposition1.TargetErosion": (65.0, "pct", "靶材侵蚀度"),
            "ns=2;s=Deposition1.DepositionRate": (8.2, "A/s", "沉积速率"),
            "ns=2;s=Deposition1.PowerKw": (55.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "靶材", "part_no": "TGT-Cu-01", "life_remaining_pct": 35, "risk": "high", "replace_lead_days": 45},
            {"name": "加热器", "part_no": "HTR-9910", "life_remaining_pct": 78, "risk": "low", "replace_lead_days": 60},
            {"name": "真空泵", "part_no": "PMP-4420", "life_remaining_pct": 62, "risk": "medium", "replace_lead_days": 30},
            {"name": "质量流量控制器", "part_no": "MFC-3080", "life_remaining_pct": 70, "risk": "low", "replace_lead_days": 45},
        ],
        power_kw_avg=55.0, power_kw_peak=80.0, coolant_flow_lpm=40.0,
        mtbf_hours=2500,
    ),
    "deposition_2": EquipmentProfile(
        equipment_id="deposition_2",
        name="Lam Vector PECVD 沉积 #2",
        type_cn="薄膜沉积",
        vendor="Lam Research",
        model="Vector Express",
        opcua_tags={
            "ns=2;s=Deposition2.Status": (True, "bool", "运行状态"),
            "ns=2;s=Deposition2.Health": (73.5, "pct", "设备健康分"),
            "ns=2;s=Deposition2.ChamberVacuum": (5e-6, "torr", "腔体真空度"),
            "ns=2;s=Deposition2.HeaterTemp": (400.0, "C", "加热器温度"),
            "ns=2;s=Deposition2.RFPower": (350.0, "W", "射频功率"),
            "ns=2;s=Deposition2.DepositionRate": (12.5, "A/s", "沉积速率"),
            "ns=2;s=Deposition2.PowerKw": (60.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "射频发生器", "part_no": "RFG-5100", "life_remaining_pct": 48, "risk": "medium", "replace_lead_days": 60},
            {"name": "加热器", "part_no": "HTR-1100", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 60},
            {"name": "真空泵", "part_no": "PMP-5530", "life_remaining_pct": 42, "risk": "high", "replace_lead_days": 30},
            {"name": "喷淋头", "part_no": "SHW-2200", "life_remaining_pct": 68, "risk": "low", "replace_lead_days": 45},
        ],
        power_kw_avg=60.0, power_kw_peak=88.0, coolant_flow_lpm=38.0,
        mtbf_hours=1800,
    ),
    "cmp_1": EquipmentProfile(
        equipment_id="cmp_1",
        name="AMAT Reflexion CMP #1",
        type_cn="化学机械抛光",
        vendor="Applied Materials",
        model="Reflexion LK",
        opcua_tags={
            "ns=2;s=CMP1.Status": (True, "bool", "运行状态"),
            "ns=2;s=CMP1.Health": (85.0, "pct", "设备健康分"),
            "ns=2;s=CMP1.PadTemp": (32.0, "C", "抛光垫温度"),
            "ns=2;s=CMP1.PadLife": (62.0, "pct", "抛光垫寿命"),
            "ns=2;s=CMP1.SlurryFlow": (250.0, "ml/min", "磨料流量"),
            "ns=2;s=CMP1.DownForce": (2.5, "psi", "下压力"),
            "ns=2;s=CMP1.PowerKw": (25.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "抛光垫", "part_no": "PAD-1001", "life_remaining_pct": 62, "risk": "medium", "replace_lead_days": 20},
            {"name": "修整器", "part_no": "DRS-2200", "life_remaining_pct": 45, "risk": "high", "replace_lead_days": 30},
            {"name": "主轴电机", "part_no": "SPL-3300", "life_remaining_pct": 78, "risk": "low", "replace_lead_days": 60},
            {"name": "磨料泵", "part_no": "SLP-4400", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 15},
        ],
        power_kw_avg=25.0, power_kw_peak=38.0, coolant_flow_lpm=25.0,
        mtbf_hours=3000,
    ),
    "inspection_1": EquipmentProfile(
        equipment_id="inspection_1",
        name="KLA 29xx 晶圆检测 #1",
        type_cn="检测/量测",
        vendor="KLA",
        model="29xx 宽光谱",
        opcua_tags={
            "ns=2;s=Inspection1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Inspection1.Health": (93.5, "pct", "设备健康分"),
            "ns=2;s=Inspection1.LaserSource": (88.0, "pct", "激光源寿命"),
            "ns=2;s=Inspection1.StagePrecision": (1.2, "nm", "晶圆台精度"),
            "ns=2;s=Inspection1.DetectionRate": (125.0, "wafer/h", "检测吞吐"),
            "ns=2;s=Inspection1.DefectSensitivity": (95.0, "pct", "缺陷灵敏度"),
            "ns=2;s=Inspection1.PowerKw": (15.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "激光源", "part_no": "LSR-5500", "life_remaining_pct": 88, "risk": "low", "replace_lead_days": 120},
            {"name": "光学系统", "part_no": "OPT-6600", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 90},
            {"name": "晶圆台", "part_no": "WFR-3340", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 60},
            {"name": "探测器", "part_no": "DTCT-7700", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 60},
        ],
        power_kw_avg=15.0, power_kw_peak=22.0, coolant_flow_lpm=12.0,
        mtbf_hours=4000,
    ),
    "implant_1": EquipmentProfile(
        equipment_id="implant_1",
        name="AMAT VIISta 900 离子注入 #1",
        type_cn="离子注入",
        vendor="Applied Materials",
        model="VIISta 900",
        opcua_tags={
            "ns=2;s=Implant1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Implant1.Health": (81.0, "pct", "设备健康分"),
            "ns=2;s=Implant1.BeamCurrent": (12.5, "mA", "束流"),
            "ns=2;s=Implant1.BeamEnergy": (180.0, "keV", "注入能量"),
            "ns=2;s=Implant1.ChamberVacuum": (2e-6, "torr", "腔体真空度"),
            "ns=2;s=Implant1.SourceLife": (58.0, "pct", "离子源寿命"),
            "ns=2;s=Implant1.PowerKw": (72.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "离子源", "part_no": "ION-8800", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 90},
            {"name": "分析磁铁", "part_no": "MAG-9900", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 120},
            {"name": "真空泵", "part_no": "PMP-6600", "life_remaining_pct": 50, "risk": "medium", "replace_lead_days": 30},
            {"name": "晶圆传输臂", "part_no": "ARM-4400", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 45},
        ],
        power_kw_avg=72.0, power_kw_peak=110.0, coolant_flow_lpm=50.0,
        mtbf_hours=1800,
    ),
    # ── 3C 精密制造典型设备（2026-07-31 扩列）──
    "smt_1": EquipmentProfile(
        equipment_id="smt_1",
        name="FUJI NXT III 贴片机 #1",
        type_cn="SMT 贴片机",
        vendor="FUJI",
        model="NXT III",
        opcua_tags={
            "ns=2;s=SMT1.Status": (True, "bool", "运行状态"),
            "ns=2;s=SMT1.Health": (84.0, "pct", "设备健康分"),
            "ns=2;s=SMT1.PlacementRate": (36000, "cph", "贴装节拍(点/小时)"),
            "ns=2;s=SMT1.FeederErr": (0.8, "pct", "喂料误差率"),
            "ns=2;s=SMT1.NozzleVac": (62.0, "kPa", "吸嘴真空度"),
            "ns=2;s=SMT1.BoardCount": (12500, "pcs", "累计贴装板数"),
            "ns=2;s=SMT1.PowerKw": (8.5, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "贴装头", "part_no": "HD-7700", "life_remaining_pct": 70, "risk": "medium", "replace_lead_days": 30},
            {"name": "喂料器", "part_no": "FD-3300", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 15},
            {"name": "吸嘴", "part_no": "NZ-1180", "life_remaining_pct": 55, "risk": "high", "replace_lead_days": 7},
            {"name": "视觉相机", "part_no": "CAM-5500", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 45},
        ],
        power_kw_avg=8.5, power_kw_peak=14.0, coolant_flow_lpm=6.0,
        mtbf_hours=3500,
    ),
    "cnc_1": EquipmentProfile(
        equipment_id="cnc_1",
        name="Brother S700X1 加工中心 #1",
        type_cn="CNC 加工中心",
        vendor="Brother",
        model="SPEEDIO S700X1",
        opcua_tags={
            "ns=2;s=CNC1.Status": (True, "bool", "运行状态"),
            "ns=2;s=CNC1.Health": (88.5, "pct", "设备健康分"),
            "ns=2;s=CNC1.SpindleLoad": (42.0, "pct", "主轴负载"),
            "ns=2;s=CNC1.SpindleTemp": (31.5, "C", "主轴温度"),
            "ns=2;s=CNC1.SpindleRpm": (12000, "rpm", "主轴转速"),
            "ns=2;s=CNC1.ToolWear": (18.0, "pct", "刀具磨损"),
            "ns=2;s=CNC1.PowerKw": (6.2, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "主轴", "part_no": "SPD-4400", "life_remaining_pct": 78, "risk": "low", "replace_lead_days": 60},
            {"name": "刀库", "part_no": "TCM-2200", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 30},
            {"name": "丝杠", "part_no": "BLS-6610", "life_remaining_pct": 62, "risk": "medium", "replace_lead_days": 45},
            {"name": "冷却泵", "part_no": "CLP-3300", "life_remaining_pct": 50, "risk": "medium", "replace_lead_days": 15},
        ],
        power_kw_avg=6.2, power_kw_peak=11.0, coolant_flow_lpm=10.0,
        mtbf_hours=4200,
    ),
    "injection_1": EquipmentProfile(
        equipment_id="injection_1",
        name="Haitian MA2500 注塑机 #1",
        type_cn="注塑机",
        vendor="Haitian",
        model="MA2500II",
        opcua_tags={
            "ns=2;s=INJ1.Status": (True, "bool", "运行状态"),
            "ns=2;s=INJ1.Health": (80.2, "pct", "设备健康分"),
            "ns=2;s=INJ1.BarrelTemp": (235.0, "C", "料筒温度"),
            "ns=2;s=INJ1.MoldTemp": (62.0, "C", "模具温度"),
            "ns=2;s=INJ1.InjPressure": (118.0, "MPa", "注射压力"),
            "ns=2;s=INJ1.CycleTime": (28.5, "s", "成型周期"),
            "ns=2;s=INJ1.PowerKw": (22.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "螺杆料筒", "part_no": "SCW-8800", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 60},
            {"name": "模具", "part_no": "MLD-4400", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 30},
            {"name": "伺服电机", "part_no": "SVX-5500", "life_remaining_pct": 80, "risk": "low", "replace_lead_days": 45},
            {"name": "液压密封", "part_no": "HYS-2200", "life_remaining_pct": 45, "risk": "high", "replace_lead_days": 15},
        ],
        power_kw_avg=22.0, power_kw_peak=40.0, coolant_flow_lpm=18.0,
        mtbf_hours=3000,
    ),
    # ── 新能源 动力电池典型设备（2026-07-31 扩列）──
    "coating_1": EquipmentProfile(
        equipment_id="coating_1",
        name="先导智能 涂布机 #1",
        type_cn="涂布机",
        vendor="先导智能",
        model="双面挤压涂布机 1400mm",
        opcua_tags={
            "ns=2;s=COAT1.Status": (True, "bool", "运行状态"),
            "ns=2;s=COAT1.Health": (86.0, "pct", "设备健康分"),
            "ns=2;s=COAT1.CoatWeight": (185.0, "g/m2", "面密度"),
            "ns=2;s=COAT1.CoatDev": (1.2, "pct", "面密度偏差"),
            "ns=2;s=COAT1.WebSpeed": (80.0, "m/min", "走带速度"),
            "ns=2;s=COAT1.DryTemp": (125.0, "C", "烘箱温度"),
            "ns=2;s=COAT1.PowerKw": (95.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "涂布模头", "part_no": "DIE-5500", "life_remaining_pct": 68, "risk": "medium", "replace_lead_days": 45},
            {"name": "背辊", "part_no": "RPL-3300", "life_remaining_pct": 75, "risk": "low", "replace_lead_days": 30},
            {"name": "纠偏系统", "part_no": "EPC-2200", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 20},
            {"name": "烘箱风机", "part_no": "FAN-6600", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 15},
        ],
        power_kw_avg=95.0, power_kw_peak=140.0, coolant_flow_lpm=5.0,
        mtbf_hours=2600,
    ),
    "winding_1": EquipmentProfile(
        equipment_id="winding_1",
        name="先导智能 卷绕机 #1",
        type_cn="卷绕/叠片机",
        vendor="先导智能",
        model="圆柱卷绕机 26/46 系列",
        opcua_tags={
            "ns=2;s=WND1.Status": (True, "bool", "运行状态"),
            "ns=2;s=WND1.Health": (83.5, "pct", "设备健康分"),
            "ns=2;s=WND1.Tension": (12.5, "N", "极片张力"),
            "ns=2;s=WND1.AlignErr": (0.25, "mm", "对齐偏差"),
            "ns=2;s=WND1.WindRate": (45.0, "ppm", "卷绕节拍(只/分)"),
            "ns=2;s=WND1.ShortRate": (35.0, "ppm", "短路不良率"),
            "ns=2;s=WND1.PowerKw": (12.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "卷针", "part_no": "NDL-4400", "life_remaining_pct": 60, "risk": "medium", "replace_lead_days": 20},
            {"name": "张力控制器", "part_no": "TNS-2200", "life_remaining_pct": 78, "risk": "low", "replace_lead_days": 30},
            {"name": "视觉对位", "part_no": "VIS-5500", "life_remaining_pct": 70, "risk": "low", "replace_lead_days": 45},
            {"name": "伺服电机", "part_no": "SVX-3300", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 30},
        ],
        power_kw_avg=12.0, power_kw_peak=20.0, coolant_flow_lpm=4.0,
        mtbf_hours=3200,
    ),
    "formation_1": EquipmentProfile(
        equipment_id="formation_1",
        name="杭可科技 化成分容柜 #1",
        type_cn="化成分容柜",
        vendor="杭可科技",
        model="高温化成容量柜 512CH",
        opcua_tags={
            "ns=2;s=FOR1.Status": (True, "bool", "运行状态"),
            "ns=2;s=FOR1.Health": (90.0, "pct", "设备健康分"),
            "ns=2;s=FOR1.ChanInUse": (498, "ch", "在用通道数"),
            "ns=2;s=FOR1.CapacityErr": (0.35, "pct", "容量分选误差"),
            "ns=2;s=FOR1.TempMax": (48.5, "C", "柜内最高温"),
            "ns=2;s=FOR1.TotalPower": (320.0, "kW", "整柜功率"),
            "ns=2;s=FOR1.PowerKw": (320.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "电源模块", "part_no": "PSU-8800", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 45},
            {"name": "温控风机", "part_no": "FAN-4400", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 15},
            {"name": "采样板", "part_no": "SMP-2200", "life_remaining_pct": 80, "risk": "low", "replace_lead_days": 30},
            {"name": "接触器", "part_no": "CNT-5500", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 20},
        ],
        power_kw_avg=320.0, power_kw_peak=420.0, coolant_flow_lpm=2.0,
        mtbf_hours=5000,
    ),
    # ── 造船 / 船舶总装制造典型设备（2026-09-11 扩列，沪东造船试点）──
    "drydock_1": EquipmentProfile(
        equipment_id="drydock_1",
        name="30万吨级干船坞 #1",
        type_cn="船坞",
        vendor="船厂自建（非标）",
        model="300K-DWT 举力式",
        opcua_tags={
            "ns=2;s=Dock1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Dock1.Health": (82.0, "pct", "设施健康分"),
            "ns=2;s=Dock1.WaterLevel": (4.2, "m", "坞室水位"),
            "ns=2;s=Dock1.BlockWeight": (18500.0, "t", "在坞总段重量"),
            "ns=2;s=Dock1.PumpFlow": (3200.0, "m3/h", "泵站排水流量"),
            "ns=2;s=Dock1.PowerKw": (210.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "闸阀门", "part_no": "GTV-9000", "life_remaining_pct": 70, "risk": "low", "replace_lead_days": 180},
            {"name": "泵站电机", "part_no": "PMP-7700", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 90},
            {"name": "坞墩", "part_no": "DBK-3300", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 120},
            {"name": "牵引绞车", "part_no": "WIN-4400", "life_remaining_pct": 62, "risk": "medium", "replace_lead_days": 60},
        ],
        power_kw_avg=210.0, power_kw_peak=340.0, coolant_flow_lpm=0.0,
        mtbf_hours=6000,
    ),
    "gantry_1": EquipmentProfile(
        equipment_id="gantry_1",
        name="900吨龙门吊 #1",
        type_cn="龙门吊",
        vendor="振华重工",
        model="ZPMC 900t Gantry",
        opcua_tags={
            "ns=2;s=Gantry1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Gantry1.Health": (88.5, "pct", "设备健康分"),
            "ns=2;s=Gantry1.HoistLoad": (620.0, "t", "当前起重量"),
            "ns=2;s=Gantry1.HoistHeight": (58.0, "m", "吊高"),
            "ns=2;s=Gantry1.WindSpeed": (8.5, "m/s", "现场风速"),
            "ns=2;s=Gantry1.PowerKw": (380.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "主起升钢丝绳", "part_no": "WR-8800", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 30},
            {"name": "大车行走电机", "part_no": "MOT-5500", "life_remaining_pct": 80, "risk": "low", "replace_lead_days": 45},
            {"name": "防风锚定", "part_no": "ANC-2200", "life_remaining_pct": 90, "risk": "low", "replace_lead_days": 60},
            {"name": "变频器", "part_no": "VFD-4400", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 30},
        ],
        power_kw_avg=380.0, power_kw_peak=560.0, coolant_flow_lpm=0.0,
        mtbf_hours=4500,
    ),
    "welding_1": EquipmentProfile(
        equipment_id="welding_1",
        name="FANUC 焊接机器人工作站 #1",
        type_cn="焊接机器人",
        vendor="FANUC",
        model="ArcMate 120iD",
        opcua_tags={
            "ns=2;s=Weld1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Weld1.Health": (90.0, "pct", "设备健康分"),
            "ns=2;s=Weld1.ArcCurrent": (280.0, "A", "焊接电流"),
            "ns=2;s=Weld1.WireFeed": (12.5, "m/min", "送丝速度"),
            "ns=2;s=Weld1.TorchTemp": (320.0, "C", "焊枪温度"),
            "ns=2;s=Weld1.DefectRate": (1.8, "pct", "焊缝缺陷率"),
            "ns=2;s=Weld1.PowerKw": (18.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "焊枪", "part_no": "TCH-1100", "life_remaining_pct": 50, "risk": "high", "replace_lead_days": 7},
            {"name": "送丝机", "part_no": "WF-3300", "life_remaining_pct": 68, "risk": "low", "replace_lead_days": 20},
            {"name": "机器人本体", "part_no": "RB-7700", "life_remaining_pct": 82, "risk": "low", "replace_lead_days": 90},
            {"name": "清枪剪丝站", "part_no": "ATC-2200", "life_remaining_pct": 60, "risk": "medium", "replace_lead_days": 15},
        ],
        power_kw_avg=18.0, power_kw_peak=30.0, coolant_flow_lpm=3.0,
        mtbf_hours=5000,
    ),
    "welding_2": EquipmentProfile(
        equipment_id="welding_2",
        name="唐山开元 焊接机器人 #2",
        type_cn="焊接机器人",
        vendor="唐山开元",
        model="OTC-TA1400",
        opcua_tags={
            "ns=2;s=Weld2.Status": (True, "bool", "运行状态"),
            "ns=2;s=Weld2.Health": (84.5, "pct", "设备健康分"),
            "ns=2;s=Weld2.ArcCurrent": (260.0, "A", "焊接电流"),
            "ns=2;s=Weld2.WireFeed": (11.0, "m/min", "送丝速度"),
            "ns=2;s=Weld2.TorchTemp": (305.0, "C", "焊枪温度"),
            "ns=2;s=Weld2.DefectRate": (2.4, "pct", "焊缝缺陷率"),
            "ns=2;s=Weld2.PowerKw": (16.5, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "焊枪", "part_no": "TCH-1200", "life_remaining_pct": 42, "risk": "high", "replace_lead_days": 7},
            {"name": "送丝机", "part_no": "WF-3400", "life_remaining_pct": 60, "risk": "medium", "replace_lead_days": 20},
            {"name": "机器人本体", "part_no": "RB-7800", "life_remaining_pct": 75, "risk": "low", "replace_lead_days": 90},
            {"name": "防飞溅嘴", "part_no": "NS-1100", "life_remaining_pct": 35, "risk": "high", "replace_lead_days": 5},
        ],
        power_kw_avg=16.5, power_kw_peak=28.0, coolant_flow_lpm=3.0,
        mtbf_hours=4800,
    ),
    "cnc_plate_1": EquipmentProfile(
        equipment_id="cnc_plate_1",
        name="梅塞尔 数控切割机 #1",
        type_cn="数控切割机",
        vendor="梅塞尔",
        model="Omnimat 激光/等离子",
        opcua_tags={
            "ns=2;s=Plate1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Plate1.Health": (86.0, "pct", "设备健康分"),
            "ns=2;s=Plate1.CutSpeed": (9.5, "m/min", "切割速度"),
            "ns=2;s=Plate1.PlateThick": (22.0, "mm", "板材厚度"),
            "ns=2;s=Plate1.GasPressure": (1.2, "bar", "切割气体压力"),
            "ns=2;s=Plate1.KerfWidth": (1.8, "mm", "割缝宽度"),
            "ns=2;s=Plate1.PowerKw": (45.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "等离子电源", "part_no": "PLS-5500", "life_remaining_pct": 55, "risk": "medium", "replace_lead_days": 45},
            {"name": "割炬", "part_no": "TCH-2200", "life_remaining_pct": 48, "risk": "high", "replace_lead_days": 10},
            {"name": "导轨", "part_no": "RL-6600", "life_remaining_pct": 80, "risk": "low", "replace_lead_days": 60},
            {"name": "除尘风机", "part_no": "FAN-3300", "life_remaining_pct": 65, "risk": "medium", "replace_lead_days": 20},
        ],
        power_kw_avg=45.0, power_kw_peak=75.0, coolant_flow_lpm=0.0,
        mtbf_hours=4000,
    ),
    "blast_paint_1": EquipmentProfile(
        equipment_id="blast_paint_1",
        name="分段抛丸涂装线 #1",
        type_cn="抛丸涂装线",
        vendor="非标集成（船厂自建）",
        model="Blast-Paint Line 24m",
        opcua_tags={
            "ns=2;s=Paint1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Paint1.Health": (83.0, "pct", "设备健康分"),
            "ns=2;s=Paint1.BlastPressure": (0.65, "MPa", "抛丸压力"),
            "ns=2;s=Paint1.PaintFlow": (140.0, "L/min", "涂布流量"),
            "ns=2;s=Paint1.SurfaceRough": (32.0, "um", "表面粗糙度"),
            "ns=2;s=Paint1.VOC": (28.0, "mg/m3", "VOC浓度"),
            "ns=2;s=Paint1.PowerKw": (120.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "抛丸叶轮", "part_no": "IMP-4400", "life_remaining_pct": 45, "risk": "high", "replace_lead_days": 15},
            {"name": "喷涂泵", "part_no": "PMP-5500", "life_remaining_pct": 60, "risk": "medium", "replace_lead_days": 20},
            {"name": "除尘滤筒", "part_no": "FLT-2200", "life_remaining_pct": 38, "risk": "high", "replace_lead_days": 7},
            {"name": "输送辊道", "part_no": "RL-3300", "life_remaining_pct": 78, "risk": "low", "replace_lead_days": 45},
        ],
        power_kw_avg=120.0, power_kw_peak=180.0, coolant_flow_lpm=8.0,
        mtbf_hours=3500,
    ),
    "marine_engine_1": EquipmentProfile(
        equipment_id="marine_engine_1",
        name="沪东重机 船用低速柴油机 #1",
        type_cn="船用柴油机",
        vendor="沪东重机",
        model="6S60ME-C8.5",
        opcua_tags={
            "ns=2;s=Engine1.Status": (True, "bool", "运行状态"),
            "ns=2;s=Engine1.Health": (91.0, "pct", "设备健康分"),
            "ns=2;s=Engine1.RPM": (89.0, "rpm", "转速"),
            "ns=2;s=Engine1.CylTemp": (420.0, "C", "缸温"),
            "ns=2;s=Engine1.OilPress": (4.8, "bar", "滑油压力"),
            "ns=2;s=Engine1.ExhaustTemp": (385.0, "C", "排气温度"),
            "ns=2;s=Engine1.FuelRate": (185.0, "g/kWh", "油耗率"),
            "ns=2;s=Engine1.PowerKw": (12500.0, "kW", "运行功率"),
        },
        key_parts=[
            {"name": "增压器", "part_no": "TC-8800", "life_remaining_pct": 72, "risk": "low", "replace_lead_days": 90},
            {"name": "缸套", "part_no": "LNR-4400", "life_remaining_pct": 58, "risk": "medium", "replace_lead_days": 120},
            {"name": "燃油泵", "part_no": "FPU-5500", "life_remaining_pct": 68, "risk": "low", "replace_lead_days": 45},
            {"name": "轴系轴承", "part_no": "BRG-6600", "life_remaining_pct": 85, "risk": "low", "replace_lead_days": 60},
        ],
        power_kw_avg=12500.0, power_kw_peak=14800.0, coolant_flow_lpm=120.0,
        mtbf_hours=20000,
    ),
}


def get_profile(eq_id: str) -> EquipmentProfile | None:
    """按设备 ID 获取配置模板。"""
    return PROFILES.get(eq_id)


def list_by_type(type_cn: str) -> list[EquipmentProfile]:
    """按设备类型中文名获取所有模板。"""
    return [p for p in PROFILES.values() if p.type_cn == type_cn]


# 中文类型名 → 设备类别代码（用于行业反查）
_CN_TO_CATEGORY: Dict[str, str] = {
    v["cn_name"]: k for k, v in EQUIPMENT_CATEGORIES.items()
}


def get_industry(eq_id: str) -> str | None:
    """按设备 ID 反查所属行业代码（semiconductor / 3c / new_energy）。"""
    p = PROFILES.get(eq_id)
    if not p:
        return None
    cat = _CN_TO_CATEGORY.get(p.type_cn)
    if not cat:
        return None
    return EQUIPMENT_CATEGORIES.get(cat, {}).get("industry")


def list_by_industry(industry: str) -> list[EquipmentProfile]:
    """按行业代码获取该行业全部设备模板。

    预设层核心入口：客户入驻声明行业后，直接拉取该行业设备模板集，
    按型号匹配后即可生成网关标签映射与 PM 种子，无需从零配置。
    """
    types = INDUSTRY_EQUIPMENT_TYPES.get(industry, [])
    cn_names = {EQUIPMENT_CATEGORIES[t]["cn_name"] for t in types if t in EQUIPMENT_CATEGORIES}
    return [p for p in PROFILES.values() if p.type_cn in cn_names]


def industry_overview() -> Dict[str, dict]:
    """行业维度的设备预设总览（供预设层汇总与入驻向导使用）。"""
    out: Dict[str, dict] = {}
    for ind, types in INDUSTRY_EQUIPMENT_TYPES.items():
        profiles = list_by_industry(ind)
        out[ind] = {
            "industry_cn": INDUSTRY_LABELS.get(ind, ind),
            "equipment_type_count": len(types),
            "equipment_types": [
                EQUIPMENT_CATEGORIES[t]["cn_name"] for t in types if t in EQUIPMENT_CATEGORIES
            ],
            "profile_count": len(profiles),
            "profile_ids": [p.equipment_id for p in profiles],
        }
    return out


def build_seed_equipment(eq_id: str) -> dict | None:
    """将设备模板转换为 PM 种子 JSON 条目。"""
    p = PROFILES.get(eq_id)
    if not p:
        return None
    import random as _r
    # 健康分：部件寿命均值*0.7 + 100*0.3 - 传感器偏差
    avg_life = sum(kp["life_remaining_pct"] for kp in p.key_parts) / len(p.key_parts)
    health = round(avg_life * 0.7 + 30, 1)
    # 随机微调使每台设备不同
    health = round(max(0, min(100, health + _r.uniform(-3, 3))), 1)
    return {
        "equipment_id": p.equipment_id,
        "name": p.name,
        "type": p.type_cn,
        "vendor": p.vendor,
        "model": p.model,
        "location": f"{p.type_cn.upper()}-BAY-{eq_id.split('_')[-1]}",
        "status": "running",
        "uptime_hours": _r.randint(2000, 9000),
        "mtbf_hours": p.mtbf_hours,
        "health_score": health,
        "last_pm": f"2026-{_r.randint(1,7):02d}-{_r.randint(1,28):02d}",
        "next_pm_due": f"2026-{_r.randint(7,9):02d}-{_r.randint(1,28):02d}",
        "sensors": {k: v[0] for k, v in p.opcua_tags.items()},
        "key_parts": p.key_parts,
        "recent_alerts": [],
        "maintenance_history": [
            {"date": f"2026-{_r.randint(1,6):02d}-{_r.randint(1,28):02d}",
             "type": "PM", "action": "定期预防维护", "cost": _r.randint(5, 30)}
        ],
    }
