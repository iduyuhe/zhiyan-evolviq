"""行业 Manifest 注册表 —— 把"行业"从代码枚举 / 硬编码字典升级为数据驱动的一等公民（V2 P1）。

设计纪律（呼应 V2 韧性降级与零真名铁律）：
- 行业 = 数据：每个行业一个 ``data/industries/<key>.json``，零代码改动即可上架新行业。
- 内置兜底 ``DEFAULT_MANIFESTS``：即使 ``data/`` 目录缺失或为空，系统仍以半导体 + 造船
  默认行为运行（沪东造船演示不依赖文件即可工作）。
- 加载失败静默降级并记日志，绝不阻断启动或请求。
- 支持按 ``key``（行业代码，如 ``shipbuilding``）或 ``label``（中文名，如 ``造船``）查询，
  兼容旧链路（企业画像存中文名）。
- manifest 内容（agent_overrides / equipment_types / router_triggers_extra / knowledge_pack /
  sample_seed）均须匿名 / 声明式，不落真名（零真名铁律）。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 项目根：src/runtime/industry_manifest.py -> parents[2] = zhiyan/
_ROOT = Path(__file__).resolve().parents[2]
_INDUSTRIES_DIR = _ROOT / "data" / "industries"


@dataclass
class IndustryManifest:
    """单个行业的声明式描述（等同一份 data/industries/<key>.json）。"""

    key: str
    label: str
    agent_overrides: dict[str, dict] = field(default_factory=dict)
    router_triggers_extra: dict[str, list] = field(default_factory=dict)
    equipment_types: list[str] = field(default_factory=list)
    knowledge_pack: str = ""
    sample_seed: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "IndustryManifest":
        return cls(
            key=d["key"],
            label=d.get("label", d["key"]),
            agent_overrides=d.get("agent_overrides", {}) or {},
            router_triggers_extra=d.get("router_triggers_extra", {}) or {},
            equipment_types=d.get("equipment_types", []) or [],
            knowledge_pack=d.get("knowledge_pack", "") or "",
            sample_seed=d.get("sample_seed", "") or "",
        )


# 内置兜底：确保无 data/industries 文件时系统仍以「全 8 行业闭枚举」正确运行
# （零回归：原 PROFILE_INDUSTRIES=8 行业、INDUSTRY_EQUIPMENT_TYPES=4 类设备全部保留）。
# JSON 文件若存在，按 key 覆盖这里的同名条目，并可新增行业（开放枚举）。
# 半导体 / 造船为富内容（agent_overrides + router_triggers_extra + equipment_types）；
# 其余为已定义枚举占位（设备表为空，待后续以 manifest 文件上架）。
DEFAULT_MANIFESTS: list[dict] = [
    {
        "key": "semiconductor",
        "label": "半导体",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": [
            "lithography",
            "etch",
            "deposition",
            "cmp",
            "inspection",
            "implant",
        ],
        "knowledge_pack": "semiconductor",
        "sample_seed": "semiconductor",
    },
    {
        "key": "3c",
        "label": "3C",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": ["smt", "cnc", "injection"],
        "knowledge_pack": "3c",
        "sample_seed": "3c",
    },
    {
        "key": "new_energy",
        "label": "新能源汽车",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": ["coating", "winding", "formation"],
        "knowledge_pack": "new_energy",
        "sample_seed": "new_energy",
    },
    {
        "key": "shipbuilding",
        "label": "造船",
        "agent_overrides": {
            "pm_maintenance": {
                "description": "造船关键设备健康诊断、预测维护建议、关键部件寿命管理",
            },
            "smt_changeover": {
                "name": "分段装配Agent",
                "description": "分段装配顺序优化与工位预配置，SMED分析+关键路径+检查清单",
                "scenarios": ["分段装配计划", "工位预配", "SMED优化", "装配检查清单"],
            },
            "aoi_judge": {
                "name": "涂装缺陷判定Agent",
                "description": "涂装/焊接缺陷智能判定，误报过滤+检测阈值优化+复判工时节省",
                "scenarios": ["误报率分析", "阈值优化", "缺陷分类", "复判效率"],
            },
            "yield_analysis": {
                "name": "一次合格率Agent",
                "description": "船体报验合格率趋势分析、缺陷分类统计、根因定位、改进建议",
                "scenarios": ["合格率趋势", "缺陷分析", "设备-质量关联"],
            },
            "quality_trace": {
                "description": "船体质量根因追溯，客诉→分段→工艺→设备→参数的端到端分析",
            },
            "dfm_check": {
                "name": "可建造性检查Agent",
                "description": "船体/舾装可建造性自动审查，焊接可达性/精度/安全规则校验",
                "scenarios": [
                    "焊接可达性",
                    "装配精度校验",
                    "安全规则",
                    "布局审查",
                    "可建造性评审报告",
                ],
            },
            "rd_npi": {
                "name": "新船型导入Agent",
                "description": "新船型项目全生命周期管理、里程碑跟踪、批量试产与风险识别",
                "scenarios": ["新船型项目", "里程碑", "项目风险", "批量试产", "船型导入"],
            },
            "ipc_standard": {
                "name": "船级社标准Agent",
                "description": "船级社标准辅助查询与缺陷判定，IACS/船级社规范+检验方法推荐",
                "scenarios": ["标准查询", "缺陷判定", "船级社规范", "检验方法"],
            },
            "eco_change": {
                "name": "设计变更Agent",
                "description": "设计/工程变更指令影响分析，受影响BOM/WIP/库存/工序识别+跨部门协同",
                "scenarios": ["变更影响分析", "在制库存评估", "行动项分发", "风险评级"],
            },
        },
        "router_triggers_extra": {
            "pm_maintenance": [
                "龙门吊",
                "焊接机器人",
                "船坞",
                "干船坞",
                "涂装线",
                "船用柴油机",
                "曲轴",
            ],
            "smt_changeover": [
                "分段装配",
                "分段建造",
                "分段合拢",
                "船体分段",
                "装配顺序",
                "舾装顺序",
            ],
            "aoi_judge": ["涂装缺陷", "焊接缺陷", "焊缝检测", "探伤"],
            "ipc_standard": ["船级社", "船级规范", "ccs", "lr", "dnv", "abs", "iacs"],
            "rd_npi": ["新船型", "船型开发", "船型导入"],
            "yield_analysis": ["一次合格率", "报验合格率", "船体合格率"],
        },
        "equipment_types": [
            "drydock",
            "gantry_crane",
            "welding_robot",
            "cnc_plate",
            "blast_paint",
            "marine_engine",
        ],
        "knowledge_pack": "shipbuilding",
        "sample_seed": "shipbuilding",
    },
    {
        "key": "telecom",
        "label": "通讯",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": [],
        "knowledge_pack": "telecom",
        "sample_seed": "telecom",
    },
    {
        "key": "photovoltaic",
        "label": "光伏",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": [],
        "knowledge_pack": "photovoltaic",
        "sample_seed": "photovoltaic",
    },
    {
        "key": "construction_machinery",
        "label": "工程机械",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": [],
        "knowledge_pack": "construction_machinery",
        "sample_seed": "construction_machinery",
    },
    {
        "key": "other",
        "label": "其他",
        "agent_overrides": {},
        "router_triggers_extra": {},
        "equipment_types": [],
        "knowledge_pack": "other",
        "sample_seed": "other",
    },
]


class ManifestRegistry:
    """行业 manifest 注册表：加载 data/industries/*.json，并以 DEFAULT_MANIFESTS 兜底。"""

    def __init__(self) -> None:
        self._by_key: dict[str, IndustryManifest] = {}
        self._by_label: dict[str, IndustryManifest] = {}
        self._load()

    def _load(self) -> None:
        # 1) 基础：内置兜底
        for d in DEFAULT_MANIFESTS:
            m = IndustryManifest.from_dict(d)
            self._by_key[m.key] = m
            self._by_label[m.label] = m
        # 2) 覆盖 / 新增：data/industries/*.json（按 key 覆盖，可新增行业）
        try:
            if _INDUSTRIES_DIR.exists():
                for f in sorted(_INDUSTRIES_DIR.glob("*.json")):
                    try:
                        d = json.loads(f.read_text(encoding="utf-8"))
                        m = IndustryManifest.from_dict(d)
                        self._by_key[m.key] = m
                        self._by_label[m.label] = m
                        logger.info(f"🧩 行业 manifest 已加载：{m.key}（{m.label}）")
                    except Exception as e:  # 单文件损坏不影响其他行业
                        logger.warning(f"⚠️ 行业 manifest 读取失败 {f.name}: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 行业 manifest 目录加载失败，使用内置兜底：{e}")

    # ── 查询 ──────────────────────────────────────────────
    def get(self, query: str | None) -> IndustryManifest | None:
        """按 key 或 label 解析行业；未命中返回 None。"""
        if not query:
            return None
        return self._by_key.get(query) or self._by_label.get(query)

    def all_manifests(self) -> list[IndustryManifest]:
        """去重（按 key）返回全部 manifest，稳定顺序。"""
        return list(self._by_key.values())

    def all_keys(self) -> list[str]:
        return sorted(self._by_key.keys())

    def all_labels(self) -> list[str]:
        return sorted(self._by_label.keys())

    # ── 维度取值（供各消费方调用）──
    def equipment_types_for(self, query: str | None) -> list[str]:
        m = self.get(query)
        return m.equipment_types if m else []

    def agent_overrides_for(self, query: str | None) -> dict[str, dict]:
        m = self.get(query)
        return m.agent_overrides if m else {}

    def router_triggers_for(self, query: str | None) -> dict[str, list[str]]:
        m = self.get(query)
        return m.router_triggers_extra if m else {}

    def knowledge_pack_for(self, query: str | None) -> str:
        m = self.get(query)
        return m.knowledge_pack if m else ""

    def sample_seed_for(self, query: str | None) -> str:
        m = self.get(query)
        return m.sample_seed if m else ""

    def collect_router_triggers(self) -> dict[str, list[str]]:
        """汇总所有行业的 router_triggers_extra，按 agent_id 聚合（供 router 注入）。"""
        out: dict[str, list[str]] = {}
        for m in self.all_manifests():
            for agent, kws in m.router_triggers_extra.items():
                out.setdefault(agent, [])
                out[agent].extend(kws)
        return out


# 进程级单例（模块导入即加载，韧性降级由 _load 保证）
manifest_registry = ManifestRegistry()
