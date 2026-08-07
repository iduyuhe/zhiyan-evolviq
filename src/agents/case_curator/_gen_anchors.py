# -*- coding: utf-8 -*-
import json

UPDATED_AT = "2026-08-04"

# recommended interface presets
IF_TELECOM = ["industry_research", "executive_cockpit", "supply_chain", "compliance_q", "cost_analysis"]
IF_CONSUMER = ["industry_research", "executive_cockpit", "supply_chain", "compliance_q", "cost_analysis"]
IF_NEWS = ["industry_research", "executive_cockpit", "supply_chain", "compliance_q", "cost_analysis", "energy_carbon"]


def anon(industry_label):
    return "某%s（研究案例·公开披露）" % industry_label


def tnote_anon(industry_label):
    return ("对外以匿名案例呈现，演示「研究案例范式」如何在%s标杆企业推演 "
            "战略 / 供应链 / 合规 / 成本四维，并对外匿名、对内真名双版教学。") % industry_label


def tnote_int(real="", code=""):
    # 🔴 零真名铁律：真实公司名/代码不在此硬编码（具体锚定存 gitignored vault，internal 视图经解析器注入）
    return ("内部锚定真实上市公司公开披露（详见 vault，internal 视图注入真名），用于校准行业研究推演；"
            "真实公司名仅在本视图出现，对外一律匿名。")


anchors = []

# ============ A. 通讯设备 / 信息通信 ============
# ---- 国内 ----
anchors.append({
    "case_id": "case_telecom_fenghuo_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 上交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "285.49 亿元", "yoy": "—"},
            {"metric": "归母净利润", "value": "7.03 亿元", "yoy": "+39.05%"},
            {"metric": "研发投入", "value": "35.78 亿元", "yoy": "占营收 12.53%"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_hengtong_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 上交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "599.84 亿元", "yoy": "+25.96%"},
            {"metric": "归母净利润", "value": "27.69 亿元", "yoy": "+28.57%"},
            {"metric": "研发投入", "value": "18.95 亿元", "yoy": "占营收 3.16%"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_zhongtian_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 上交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "480.55 亿元", "yoy": "+6.63%"},
            {"metric": "归母净利润", "value": "28.38 亿元", "yoy": "-8.94%"},
            {"metric": "研发投入", "value": "19.44 亿元", "yoy": "占营收 4.04%"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_ziguang_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "790.24 亿元", "yoy": "+2.22%"},
            {"metric": "归母净利润", "value": "15.72 亿元", "yoy": "-25.23%"},
            {"metric": "研发投入", "value": "51.02 亿元", "yoy": "—"},
            {"metric": "控股子公司新华三营收", "value": "550.74 亿元", "yoy": "—", "note": "算力 / ICT 基础设施核心主体"}
        ]
    }
})

# ---- 全球 ----
anchors.append({
    "case_id": "case_telecom_ericsson_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资通讯企业 Annual Report 2024 / Q4 & Full-year report 2024（2025-01-24 披露；公司官网 / SEC 20-F 交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "净销售额", "value": "2479 亿瑞典克朗", "yoy": "-6%"},
            {"metric": "净利润", "value": "3.7 亿瑞典克朗", "yoy": "扭亏（2023 年为 -261 亿亏损）"},
            {"metric": "研发投入", "value": "535 亿瑞典克朗", "yoy": "占营收约 21.6%"},
            {"metric": "毛利率", "value": "44.1%", "yoy": "+5.5pct"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_nokia_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资通讯企业 2024 Financial Report（2025-01-30 披露；公司官网 / SEC 6-K 交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "净销售额", "value": "192.2 亿欧元", "yoy": "-9%"},
            {"metric": "营业利润", "value": "20.0 亿欧元", "yoy": "+20%（报告口径）"},
            {"metric": "净利润（本期）", "value": "12.8 亿欧元", "yoy": "+89%"},
            {"metric": "研发投入", "value": "45.1 亿欧元", "yoy": "+5%"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_cisco_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资企业 FY2024 Form 10-K（财年截至 2024-07-27；2024-09 披露；SEC / 公司财报交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "总营收", "value": "538.0 亿美元", "yoy": "-6%"},
            {"metric": "净利润", "value": "103.2 亿美元", "yoy": "-18%"},
            {"metric": "研发投入", "value": "79.8 亿美元", "yoy": "+6%"},
            {"metric": "毛利率", "value": "64.7%", "yoy": "+2.0pct"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_ciena_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资企业 FY2024 Form 10-K（财年截至 2024-11-02；2024-12 披露；SEC / 财报新闻稿交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "总营收", "value": "40.1 亿美元", "yoy": "-8.5%"},
            {"metric": "净利润（GAAP）", "value": "0.84 亿美元", "yoy": "-67%"},
            {"metric": "研发投入", "value": "7.67 亿美元", "yoy": "+2.3%"},
            {"metric": "毛利率", "value": "42.8%", "yoy": "持平"}
        ]
    }
})

anchors.append({
    "case_id": "case_telecom_juniper_2024",
    "subject_anon": anon("通讯设备企业"),
    "industry": "通讯设备 / 信息通信",
    "industry_key": "telecom",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_TELECOM,
    "teaching_notes_anon": tnote_anon("通讯设备"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资企业 FY2024 Form 10-K（财年截至 2024-12-31；2025-02 披露；SEC / 财报新闻稿交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "总营收", "value": "50.7 亿美元", "yoy": "-8.8%"},
            {"metric": "净利润", "value": "2.88 亿美元", "yoy": "-7.2%"},
            {"metric": "研发投入", "value": "11.5 亿美元", "yoy": "+0.5%"},
            {"metric": "毛利率", "value": "58.8%", "yoy": "+1.2pct"}
        ]
    }
})

# ============ B. 消费电子 / 智能终端 ============
# ---- 国内 ----
anchors.append({
    "case_id": "case_consumer_electronics_goertek_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "1009.54 亿元", "yoy": "—"},
            {"metric": "归母净利润", "value": "26.65 亿元", "yoy": "+144.93%"},
            {"metric": "研发投入", "value": "45.69 亿元", "yoy": "占营收 4.53%"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_lens_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "698.97 亿元", "yoy": "+28.27%"},
            {"metric": "归母净利润", "value": "36.24 亿元", "yoy": "+19.94%"},
            {"metric": "研发投入", "value": "27.85 亿元", "yoy": "—"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_fii_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 上交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "6091.35 亿元", "yoy": "+27.88%"},
            {"metric": "归母净利润", "value": "232.16 亿元", "yoy": "+10.34%"},
            {"metric": "研发投入", "value": "106.3 亿元", "yoy": "—"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_transsion_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 上交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "687.15 亿元", "yoy": "+10.31%"},
            {"metric": "归母净利润", "value": "55.49 亿元", "yoy": "+0.22%"},
            {"metric": "研发投入", "value": "25.17 亿元", "yoy": "占营收 3.66%"},
            {"metric": "手机出货量", "value": "2.01 亿部", "yoy": "—", "note": "新兴市场智能机龙头"}
        ]
    }
})

# ---- 全球 ----
anchors.append({
    "case_id": "case_consumer_electronics_honhai_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资代工企业 2024 年报 / 2024Q4 法说会（2025-03 披露；公司官网 / 台湾证交所交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业收入", "value": "6.86 万亿新台币", "yoy": "+11.3%"},
            {"metric": "净利润", "value": "1527 亿新台币", "yoy": "—"},
            {"metric": "每股收益（EPS）", "value": "11.01 元新台币", "yoy": "—"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_sony_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电子企业 FY2024 Consolidated Results（财年截至 2025-03-31；2025-05-14 披露；公司 IR / SEC 6-K 交叉核对；注：FY2024 跨 2024.4–2025.3）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "销售额", "value": "12.96 万亿日元", "yoy": "约持平（-0%）"},
            {"metric": "归母净利润", "value": "1.14 万亿日元", "yoy": "+18%"},
            {"metric": "研发投入", "value": "7427.7 亿日元", "yoy": "+1.0%"},
            {"metric": "营业利润率", "value": "10.9%", "yoy": "+1.6pct"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_apple_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资消费电子企业 FY2024 Form 10-K（财年截至 2024-09-28；2024-11 披露；SEC / 公司 10-K 交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "净销售额", "value": "3910.4 亿美元", "yoy": "+2%"},
            {"metric": "净利润", "value": "937.4 亿美元", "yoy": "—"},
            {"metric": "研发投入", "value": "314.0 亿美元", "yoy": "+4.9%"},
            {"metric": "服务业务营收", "value": "961.7 亿美元", "yoy": "+12.9%", "note": "高毛利服务引擎"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_samsung_electronics_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资半导体企业 2024 Annual Report（2025 年披露；公司官网 / 财报新闻稿交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营收", "value": "300.9 万亿韩元", "yoy": "—"},
            {"metric": "营业利润", "value": "32.7 万亿韩元", "yoy": "—"},
            {"metric": "净利润", "value": "34.5 万亿韩元", "yoy": "—"}
        ]
    }
})

anchors.append({
    "case_id": "case_consumer_electronics_lg_electronics_2024",
    "subject_anon": anon("消费电子企业"),
    "industry": "消费电子 / 智能终端",
    "industry_key": "consumer_electronics",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_CONSUMER,
    "teaching_notes_anon": tnote_anon("消费电子"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电子企业 2024 Financial Results（2025-01-24 披露；公司官网 / 投资者关系交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营收", "value": "87.73 万亿韩元", "yoy": "+6.6%"},
            {"metric": "营业利润", "value": "3.42 万亿韩元", "yoy": "-6.4%"},
            {"metric": "净利润", "value": "591 亿韩元", "yoy": "-48.7%"}
        ]
    }
})

# ============ C. 新能源 / 动力电池与储能 ============
# ---- 国内 ----
anchors.append({
    "case_id": "case_new_energy_byd_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "7771 亿元", "yoy": "+29%"},
            {"metric": "归母净利润", "value": "402.5 亿元", "yoy": "+34%"},
            {"metric": "研发投入", "value": "542 亿元", "yoy": "—"},
            {"metric": "新能源汽车销量 / 市占率", "value": "427 万辆 / 33.2%", "yoy": "—", "note": "国内新能源乘用车销量第一"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_eve_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "486.15 亿元", "yoy": "-0.3%"},
            {"metric": "归母净利润", "value": "40.76 亿元", "yoy": "+0.63%"},
            {"metric": "研发投入", "value": "30.6 亿元", "yoy": "占营收 6.29%"},
            {"metric": "储能电池出货量", "value": "50.45 GWh", "yoy": "—", "note": "储能为增长主力"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_sungrow_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "778.57 亿元", "yoy": "+7.8%"},
            {"metric": "归母净利润", "value": "110.36 亿元", "yoy": "+16.92%"},
            {"metric": "研发投入", "value": "31.64 亿元", "yoy": "占营收 4.06%"},
            {"metric": "储能系统发货 / 光伏逆变器发货", "value": "28 GWh / 147 GW", "yoy": "—", "note": "储能 + 逆变器双龙头"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_guoxuan_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "domestic",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "2024 年年度报告（2025 年 4 月披露；公司公告 / 深交所 / 证券媒体交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业总收入", "value": "353.92 亿元", "yoy": "+11.98%"},
            {"metric": "归母净利润", "value": "12.07 亿元", "yoy": "+28.56%"},
            {"metric": "研发投入", "value": "29.29 亿元", "yoy": "占营收 8.28%"},
            {"metric": "海外地区收入", "value": "110.05 亿元", "yoy": "+71.21%", "note": "出海加速"}
        ]
    }
})

# ---- 全球 ----
anchors.append({
    "case_id": "case_new_energy_lg_energy_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电池企业 2024 Financial Results（2025-01-24 披露；公司官网 / 财报新闻稿交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业收入", "value": "25.6 万亿韩元", "yoy": "-24.1%"},
            {"metric": "营业利润", "value": "575.4 亿韩元", "yoy": "-73.4%"},
            {"metric": "净利润", "value": "338.6 亿韩元", "yoy": "-79.3%"},
            {"metric": "营业利润率", "value": "2.2%", "yoy": "-5.4pct", "note": "含 IRA 税收抵免影响"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_panasonic_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电子企业 FY2025 Financial Results（财年截至 2025-03-31；2025-05-09 披露；公司官网 / 财报新闻稿交叉核对；注：FY2025 跨 2024.4–2025.3，为其最新完整财年）",
        "fiscal_year": 2025,
        "facts": [
            {"metric": "营业收入", "value": "8.46 万亿日元", "yoy": "-0.5%"},
            {"metric": "营业利润", "value": "4265 亿日元", "yoy": "+18.2%"},
            {"metric": "归母净利润", "value": "3662 亿日元", "yoy": "-17.5%"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_samsung_sdi_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电池企业 2024 Annual Report（2025 年披露；公司官网 / 财报新闻稿交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "营业收入", "value": "16.59 万亿韩元", "yoy": "—"},
            {"metric": "营业利润", "value": "363.3 亿韩元", "yoy": "—"},
            {"metric": "净利润", "value": "575.5 亿韩元", "yoy": "—"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_tesla_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资新能源企业 FY2024 Form 10-K（财年截至 2024-12-31；2025-01 披露；SEC / 公司 10-K 交叉核对）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "总营收", "value": "976.9 亿美元", "yoy": "+1%"},
            {"metric": "净利润（归母）", "value": "70.9 亿美元", "yoy": "-53%"},
            {"metric": "研发投入", "value": "45.4 亿美元", "yoy": "—"},
            {"metric": "储能部署量", "value": "31.4 GWh", "yoy": "创纪录", "note": "能源 / 储能业务核心指标"}
        ]
    }
})

anchors.append({
    "case_id": "case_new_energy_sk_on_2024",
    "subject_anon": anon("新能源企业"),
    "industry": "新能源 / 动力电池与储能",
    "industry_key": "new_energy",
    "real_anchor": "__VAULTED__",
    "scope": "global",
    "recommended_interfaces": IF_NEWS,
    "teaching_notes_anon": tnote_anon("新能源"),
    "teaching_notes_internal": tnote_int(),
    "status": "active",
    "updated_at": UPDATED_AT,
    "disclosure_facts": {
        "source": "目标外资电池企业 2024 年报（电池子公司 其电池子公司 口径；2025-02 披露；公司年报 / 券商研报交叉核对；注：其电池子公司 为子公司，数据取自 目标外资电池企业 合并报表中的电池业务分部）",
        "fiscal_year": 2024,
        "facts": [
            {"metric": "电池业务营收", "value": "46 亿美元", "yoy": "-53%"},
            {"metric": "营业利润", "value": "-8.3 亿美元（亏损）", "yoy": "亏损扩大（2023 为 -4.5 亿）"},
            {"metric": "符合 IRA 补贴出货量", "value": "6.1 GWh", "yoy": "-54%", "note": "北美政策敏感"}
        ]
    }
})

# ---- 写出 ----
out_path = "E:/agent_industry/zhiyan/src/agents/case_curator/_new_anchors.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(anchors, f, ensure_ascii=False, indent=2)

print("WROTE", len(anchors), "anchors ->", out_path)
