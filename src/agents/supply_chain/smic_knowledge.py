"""SMIC半导体供应链知识库——Agent行业知识

为Agent提供半导体制造供应链的领域知识，
使其输出更贴合SMIC业务场景。
"""

# 半导体关键物料知识
SEMI_MATERIAL_KNOWLEDGE = {
    "硅片": {
        "description": "晶圆制造基础材料，分8英寸/12英寸",
        "criticality": "高",
        "lead_time_range": "30-60天",
        "supply_risk": "进口依赖度高，国产替代进度加快",
        "storage": "恒温恒湿，无特殊有效期",
        "typical_suppliers": ["上海硅产业集团", "中环股份", "上海新傲", "SUMCO", "信越化学"],
    },
    "光刻胶": {
        "description": "光刻工艺核心材料，分ArF/KrF/i-line",
        "criticality": "极高",
        "lead_time_range": "20-45天",
        "supply_risk": "高端ArF光刻胶进口依赖极高，国产替代验证中",
        "storage": "2-8°C冷藏，有有效期(6-12个月)",
        "typical_suppliers": ["JSR", "TOK", "信越化学", "北京科华", "南大光电", "徐州博康"],
    },
    "特种气体": {
        "description": "刻蚀/沉积/清洗工艺用高纯气体",
        "criticality": "高",
        "lead_time_range": "7-30天",
        "supply_risk": "部分气体需危化品许可，供应集中",
        "storage": "钢瓶存储，需安全监控",
        "typical_suppliers": ["华特气体", "杭氧股份", "中船重工718所"],
    },
    "靶材": {
        "description": "物理气相沉积(PVD)工艺用高纯金属靶",
        "criticality": "高",
        "lead_time_range": "30-45天",
        "supply_risk": "高纯金属靶材国产替代加速中",
        "storage": "真空封装，防氧化",
        "typical_suppliers": ["江丰电子", "有研新材", "Tosoh", "Honeywell"],
    },
    "CMP材料": {
        "description": "化学机械抛光用抛光液和抛光垫",
        "criticality": "中",
        "lead_time_range": "20-30天",
        "supply_risk": "国产替代已取得进展",
        "storage": "抛光液有有效期",
        "typical_suppliers": ["安集科技", "鼎龙股份", "Cabot", "Dow"],
    },
}

# SMIC供应链关键业务规则
BUSINESS_RULES = """
## SMIC供应链管理规则

1. **齐套率目标**：28nm产线关键物料齐套率目标≥85%
2. **预警阈值**：物料库存低于安全库存120%时触发预警
3. **国产替代优先级**：同等条件下优先推荐国产供应商
4. **紧急采购**：缺料影响产线时，允许5%以内的价格溢价采购
5. **供应商评级**：每季度基于OTD/质量/价格综合评分
6. **安全库存**：进口物料≥60天，国产物料≥30天
7. **光刻胶有效期管理**：到货起算，剩余有效期<3个月自动预警
"""

# 演示场景建议
DEMO_SCENARIOS = {
    "smic_28nm_check": {
        "name": "28nm产线物料齐套检查",
        "description": "检查SMIC 28nm逻辑工艺产线的12项关键物料供应状态",
        "suggested_goal": "检查SMIC-28nm-Logic BOM的物料供应，重点关注硅片和光刻胶，缺料风险>30%时自动检索替代方案",
        "expected_outcome": "齐套率40-60%区间，发现2-4项严重缺料",
    },
    "smic_photoresist": {
        "name": "光刻胶供应专项检查",
        "description": "专项检查ArF/KrF/i-line光刻胶的库存和替代方案",
        "suggested_goal": "检查三款光刻胶的库存和PO交期，ArF光刻胶重点关注国产替代方案",
        "expected_outcome": "展示国产/进口替代方案对比",
    },
    "smic_alternative": {
        "name": "国产替代可行性评估",
        "description": "评估关键物料的国产替代可行性，输出量化对比",
        "suggested_goal": "对硅片、光刻胶、靶材的进口物料，检索国产替代方案并对比价格/交期",
        "expected_outcome": "展示6组国产替代方案对比数据",
    },
}
