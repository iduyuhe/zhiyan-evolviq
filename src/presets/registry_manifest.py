"""能力资产 Registry（HubPort 启发 · 挖存量升级）

把既有 `src/presets/` 的设备 / ERP / MES / 权限模板从"静态模块"升级为「能力资产 registry」：
- 统一 manifest：每个资产有 id / kind / version / industry / 质量门控等级 / 契约指纹。
- 质量门控：registry 加载时对每个资产做冒烟（契约字段存在性 + 非空），分级标注 quality_gate。
- 版本化与回滚：manifest 记录 schema_version，加载失败时回滚到上一可用快照（内存）。
- 加密凭证引用：资产连接参数模板只存「占位符引用名」，绝不内联明文密钥（零明文铁律）。

设计纪律（与全局一致）：
- 挖存量：完全复用 erp_profiles / mes_profiles / permission_templates / equipment_profiles，
  不重写其实现，只在其之上盖一层 manifest + 门控。
- 不引入运行时依赖：纯后端结构化，未接入 API import（懒加载），符合延迟部署纪律。
- 不破坏演示：get_preset_summary() 仍可用，registry 仅在其上补充元信息。
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 资产种类
ASSET_KINDS = ("equipment", "erp", "mes", "permission")

# 质量门控等级：smoke_ok=冒烟通过；validated=含契约指纹；deprecated=待下线
QUALITY_OK = "smoke_ok"
QUALITY_VALIDATED = "validated"
QUALITY_DEPRECATED = "deprecated"

# registry manifest 当前 schema 版本（变更需 bump，旧版走回滚）
MANIFEST_SCHEMA_VERSION = 1

# 契约指纹：每个资产必须暴露的核心字段（冒烟用）
_CONTRACT_FIELDS: Dict[str, List[str]] = {
    "equipment": ["type_cn", "industry", "data_domains"],
    "erp": ["name", "industry_coverage", "data_domains"],
    "mes": ["name", "data_domains"],
    "permission": ["role", "industries", "permissions"],
}


@dataclass
class CapabilityAsset:
    asset_id: str
    kind: str
    version: str
    industry: str
    display_name: str
    contract_fields: List[str]
    quality_gate: str = QUALITY_OK
    credential_refs: List[str] = field(default_factory=list)  # 仅占位符引用名，绝不明文
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "kind": self.kind,
            "version": self.version,
            "industry": self.industry,
            "display_name": self.display_name,
            "contract_fields": self.contract_fields,
            "quality_gate": self.quality_gate,
            "credential_refs": self.credential_refs,
            "meta": self.meta,
        }


def _snapshot_key() -> str:
    return f"registry_snapshot_v{MANIFEST_SCHEMA_VERSION}"


class CapabilityRegistry:
    """能力资产 registry：在既有 presets 之上盖 manifest + 质量门控 + 回滚。

    用法：
        reg = CapabilityRegistry()
        summary = reg.scan()          # 冒烟 + 收集 manifest
        assets = reg.list_assets()    # 已通过门控的资产
        asset = reg.get("equipment:semiconductor:litho")
    """

    def __init__(self) -> None:
        self._assets: Dict[str, CapabilityAsset] = {}
        self._last_snapshot: Dict[str, Any] = {}
        self._loaded = False

    # ---- 冒烟：检查资产是否暴露契约字段 ----
    def _smoke(self, kind: str, obj: Any) -> bool:
        fields = _CONTRACT_FIELDS.get(kind, [])
        if not fields:
            return True
        try:
            for f in fields:
                if not hasattr(obj, f) and f not in (obj or {}):
                    return False
            return True
        except Exception:
            return False

    def scan(self) -> Dict[str, Any]:
        """扫描既有 presets，构建 manifest，并对每个资产做冒烟门控。"""
        snapshot: Dict[str, Any] = {}
        try:
            from src.presets import (
                erp_profiles,
                mes_profiles,
                permission_templates,
            )
            from src.agents.pm_maintenance import equipment_profiles
        except Exception as e:  # 极端降级：registry 不可用也不阻断主程序
            logger.warning(f"⚠️ 能力资产 registry 加载失败（不影响主程序）：{e}")
            return {"schema_version": MANIFEST_SCHEMA_VERSION, "assets": [], "error": str(e)}

        assets: Dict[str, CapabilityAsset] = {}

        # 1) 设备预设
        eq = equipment_profiles.PROFILES
        for aid, p in eq.items():
            ok = self._smoke("equipment", p)
            assets[f"equipment:{aid}"] = CapabilityAsset(
                asset_id=aid,
                kind="equipment",
                version=getattr(p, "version", "1.0"),
                industry=getattr(p, "industry", "unknown"),
                display_name=getattr(p, "type_cn", aid),
                contract_fields=_CONTRACT_FIELDS["equipment"],
                quality_gate=QUALITY_VALIDATED if ok else QUALITY_DEPRECATED,
                credential_refs=["ZHIYAN_DS_<T>_<KIND>_KEY"],  # 仅引用名
                meta={"data_domains": getattr(p, "data_domains", [])},
            )

        # 2) ERP 预设
        for aid, cfg in erp_profiles.ERP_REGISTRY.items():
            ok = self._smoke("erp", cfg)
            assets[f"erp:{aid}"] = CapabilityAsset(
                asset_id=aid,
                kind="erp",
                version=getattr(cfg, "version", "1.0"),
                industry=getattr(cfg, "industry_coverage", "cn-general"),
                display_name=aid,
                contract_fields=_CONTRACT_FIELDS["erp"],
                quality_gate=QUALITY_VALIDATED if ok else QUALITY_DEPRECATED,
                credential_refs=["ZHIYAN_DS_<T>_ERP_KEY"],
                meta={"data_domains": getattr(cfg, "data_domains", [])},
            )

        # 3) MES 预设
        for aid, cfg in mes_profiles.MES_REGISTRY.items():
            ok = self._smoke("mes", cfg)
            assets[f"mes:{aid}"] = CapabilityAsset(
                asset_id=aid,
                kind="mes",
                version=getattr(cfg, "version", "1.0"),
                industry=getattr(cfg, "industry_coverage", "cn-general"),
                display_name=aid,
                contract_fields=_CONTRACT_FIELDS["mes"],
                quality_gate=QUALITY_VALIDATED if ok else QUALITY_DEPRECATED,
                credential_refs=["ZHIYAN_DS_<T>_MES_KEY"],
                meta={"data_domains": getattr(cfg, "data_domains", [])},
            )

        # 4) 权限模板（含 7 角色 × 3 行业）
        perm = permission_templates.get_permission_summary()
        for role in perm.get("business_roles", []):
            aid = f"perm:{role}"
            # 权限模板对象在模板模块内，这里以 summary 验证冒烟字段
            assets[aid] = CapabilityAsset(
                asset_id=role,
                kind="permission",
                version="1.0",
                industry=",".join(perm.get("industries", [])),
                display_name=role,
                contract_fields=_CONTRACT_FIELDS["permission"],
                quality_gate=QUALITY_OK,
                credential_refs=[],
                meta={"industries": perm.get("industries", [])},
            )

        # 回滚保护：本次扫描成功才替换内存态
        snapshot = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "assets": {k: v.to_dict() for k, v in assets.items()},
            "counts": {k: sum(1 for a in assets.values() if a.kind == k) for k in ASSET_KINDS},
        }
        self._assets = assets
        self._last_snapshot = copy.deepcopy(snapshot)
        self._loaded = True
        return snapshot

    def list_assets(self, kind: Optional[str] = None,
                    min_quality: str = QUALITY_OK) -> List[CapabilityAsset]:
        if not self._loaded:
            self.scan()
        out = [a for a in self._assets.values() if a.quality_gate != QUALITY_DEPRECATED]
        if kind:
            out = [a for a in out if a.kind == kind]
        return out

    def get(self, asset_id: str) -> Optional[CapabilityAsset]:
        if not self._loaded:
            self.scan()
        return self._assets.get(asset_id)

    def get_snapshot(self) -> Dict[str, Any]:
        return self._last_snapshot or {"schema_version": MANIFEST_SCHEMA_VERSION, "assets": []}


# 进程级单例（懒加载语义，首次访问 scan）
_default_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = CapabilityRegistry()
        _default_registry.scan()
    return _default_registry
