"""质量决策脑工具集：五类干预目录 + UNS 质量事件映射。

质量版「五类干预」与 APS 造船感知的五类干预对齐，形成平台级决策脑范式：
① 缺陷预警 ② 误报抑制 ③ 良率保卫 ④ 追溯触发 ⑤ CAPA 闭环
"""

# 五类干预静态目录（顺序固定，供前端/看板稳定渲染）
INTERVENTION_CATALOG: dict[str, str] = {
    "defect_forecast": "缺陷预警",
    "false_alarm_suppression": "误报抑制",
    "yield_defense": "良率保卫",
    "trace_trigger": "追溯触发",
    "capa_loop": "CAPA 闭环",
}

# UNS 质量事件类型 → 触发的干预类（事件驱动入口映射）
EVENT_TO_INTERVENTIONS: dict[str, list[str]] = {
    "aoi": ["false_alarm_suppression", "defect_forecast"],
    "spc": ["defect_forecast"],
    "complaint": ["trace_trigger", "capa_loop"],
    "equipment": ["yield_defense"],
    "batch": ["capa_loop", "trace_trigger"],
}


def catalog_zh(code: str) -> str:
    """干预类型码 → 中文标签。"""
    return INTERVENTION_CATALOG.get(code, code)


def intervention_order() -> list[str]:
    """五类干预的固定顺序（保证输出稳定）。"""
    return list(INTERVENTION_CATALOG.keys())
