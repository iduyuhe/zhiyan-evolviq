"""智衍 EvolvIQ · 预设层（Presets Layer）

"不等客户签约，先把行业典型设备、系统、接口全部建好。
客户来了直接匹配模板，数日对接完成。"

—— 杜总 2026-07-29 战略定调

包含：
- equipment_profiles: 设备预设（3 行业 12 类 15 台：半导体 6类9台 / 3C 3类3台 / 新能源 3类3台）
- erp_profiles: ERP 系统预设（7 套覆盖中国制造业 90%+）
- mes_profiles: MES 系统预设（4 套覆盖主流国产/进口）
- permission_templates: 权限模板预设（7 岗位 × 3 行业，入驻勾选即配权）

每一套预设包含：
1. 基础信息（名称/版本/典型行业）
2. 数据接口方式（API / DB / OPC-UA / 文件）
3. 可消费数据域（财务/采购/销售/库存/BOM/生产/品质/设备）
4. 对应 Agent 映射（哪些智能体消费哪些数据域）
5. 连接参数模板（客户接入时填写具体 IP/端口/密钥）
"""

from src.presets import erp_profiles, mes_profiles, permission_templates
from src.agents.pm_maintenance import equipment_profiles


def get_preset_summary() -> dict:
    """返回预设层全局摘要（用于「企业入驻」接口推荐）。"""
    erp = erp_profiles.ERP_REGISTRY
    mes = mes_profiles.MES_REGISTRY
    eq = equipment_profiles.PROFILES
    perm = permission_templates.get_permission_summary()
    return {
        "erp_count": len(erp),
        "erp_list": list(erp.keys()),
        "mes_count": len(mes),
        "mes_list": list(mes.keys()),
        "equipment_count": len(eq),
        "equipment_types": sorted(set(p.type_cn for p in eq.values())),
        "equipment_industry_count": len(equipment_profiles.INDUSTRY_EQUIPMENT_TYPES),
        "equipment_by_industry": equipment_profiles.industry_overview(),
        "permission_role_count": perm["business_role_count"],
        "permission_roles": perm["business_roles"],
        "permission_industries": perm["industries"],
        "estimated_coverage": {
            "erp": "覆盖中国制造业 ERP 90%+（SAP/用友/金蝶/Oracle/浪潮）",
            "mes": "覆盖主流进口+国产 MES 85%+（西门子/罗克韦尔/霍尼韦尔/国产通用）",
            "equipment": "半导体 Fab 6 类 + 3C 精密制造 3 类(SMT/CNC/注塑) + 新能源动力电池 3 类(涂布/卷绕/化成分容)；共 3 行业 12 类设备（可继续按行业扩展）",
            "permission": "7 类标准岗位 × 3 行业专属覆盖，入驻勾选即配权",
        },
    }
