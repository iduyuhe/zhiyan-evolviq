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
}

# ── 行业归属映射（预设层：客户入驻选行业 → 自动匹配该行业设备模板）──
# key = 行业代码，value = 该行业的设备类型列表
INDUSTRY_EQUIPMENT_TYPES: Dict[str, List[str]] = {
    "semiconductor": ["lithography", "etch", "deposition", "cmp", "inspection", "implant"],
    "3c": ["smt", "cnc", "injection"],
    "new_energy": ["coating", "winding", "formation"],
}

INDUSTRY_LABELS: Dict[str, str] = {
    "semiconductor": "半导体 / 集成电路晶圆制造",
    "3c": "3C 消费电子 / 精密制造",
    "new_energy": "新能源 / 动力电池与储能",
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
