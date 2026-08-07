"""技能资产化 v0.1（自我进化闭环 · 资产通道 SKILL 的真实落库）

设计来源：evolution_loop 已把「idea（终审改进建议）/ contradicted（执行不符）」信号
路由到 asset_target=ASSET_SKILL，但只产出泛化「提议草稿」文本，没有真正的技能资产。

本模块补齐「技能从真实终审记录长出」的最小可用落库：
- SkillAssetStore（SQLite，与 evolution_loop 同底座）：把一条 SKILL 信号落成
  一条技能候选（status=proposed），供人工审批门 approve → approved，或 archive 驳回。
- 零真名：技能描述一律 desensitize 后入库，绝不携带企业真名 / PII。
- 生命周期：proposed 超过 TTL 自动归档（lifecycle_gc），避免草稿无限堆积。

铁律（与 evolution_loop 一致）：
- 自进化**绝不自动应用**任何技能变更，必须人工 approve；本库默认 status=proposed。
- 挖存量：仅消费既有 EvaluationSignal，不新增 REST 端点 / agent / 案例。
- 韧性：SQLite 不可用 → 降级纯内存 dict，不破管。
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.common.leak import sanitize_leak
from src.runtime.evolution_loop import EvaluationSignal, ASSET_SKILL

# proposed 草稿存活期（天）：超过自动归档，收敛记忆资产
PROPOSED_TTL_DAYS = 30


@dataclass
class SkillAsset:
    """一条技能资产候选（从真实终审记录长出）。"""

    skill_id: str
    name: str
    description: str
    source_signal_id: str
    agent: str
    industry_key: str = ""
    tenant: str = "default"
    status: str = "proposed"  # proposed → approved（人工审批）/ archived（驳回或过期）
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None
    decided_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source_signal_id": self.source_signal_id,
            "agent": self.agent,
            "industry_key": self.industry_key,
            "tenant": self.tenant,
            "status": self.status,
            "created_at": self.created_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
        }


def _derive_name(sig: EvaluationSignal) -> str:
    """从信号派生技能候选名（脱敏，简洁）。"""
    base = (sig.payload.get("text") or "").strip()
    # 取首句前 18 字作为名字素材，避免过长
    first = base.replace("\n", " ").split("。")[0][:18] or sig.signal_kind
    return f"技能候选·{sig.agent}·{first}"


class SkillAssetStore:
    """技能资产库（SQLite 落库，零真名，人工审批门）。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.environ.get(
            "ZHIYAN_SKILL_ASSET_DB", os.environ.get("ZHIYAN_EVOLUTION_DB", "./zhiyan_evolution.db")
        )
        self._db_enabled = self._db_path.lower() != "disabled"
        self._mem: Dict[str, SkillAsset] = {}
        if self._db_enabled:
            self._init_db()
            self._load()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS skill_assets (
                        skill_id TEXT PRIMARY KEY,
                        name TEXT, description TEXT, source_signal_id TEXT,
                        agent TEXT, industry_key TEXT, tenant TEXT,
                        status TEXT, created_at REAL, decided_at REAL, decided_by TEXT
                    )"""
                )
        except Exception:  # noqa: BLE001  韧性：SQLite 失败降级纯内存
            self._db_enabled = False

    def _load(self) -> None:
        if not self._db_enabled:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT skill_id,name,description,source_signal_id,agent,"
                    "industry_key,tenant,status,created_at,decided_at,decided_by "
                    "FROM skill_assets"
                ).fetchall()
            for r in rows:
                self._mem[r[0]] = SkillAsset(*r)
        except Exception:  # noqa: BLE001
            pass

    def ingest_from_signal(self, sig: EvaluationSignal) -> Optional[SkillAsset]:
        """把一条 SKILL 信号落库为技能候选。同一 source_signal_id 幂等（不重复）。"""
        if sig.asset_target != ASSET_SKILL:
            return None
        # 幂等：同信号已落过则直接返回
        for s in self._mem.values():
            if s.source_signal_id == sig.signal_id:
                return s
        raw = sig.payload.get("text") or ""
        safe_desc = sanitize_leak(raw)[:512] or "（无描述）"
        sk = SkillAsset(
            skill_id=f"sk-{uuid.uuid4().hex[:12]}",
            name=_derive_name(sig),
            description=safe_desc,
            source_signal_id=sig.signal_id,
            agent=sig.agent,
            industry_key=sig.industry_key,
            tenant="default",
        )
        self._mem[sk.skill_id] = sk
        if self._db_enabled:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO skill_assets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (sk.skill_id, sk.name, sk.description, sk.source_signal_id,
                         sk.agent, sk.industry_key, sk.tenant, sk.status,
                         sk.created_at, sk.decided_at, sk.decided_by),
                    )
            except Exception:  # noqa: BLE001
                pass
        return sk

    def approve(self, skill_id: str, by: str = "admin") -> bool:
        return self._decide(skill_id, "approved", by)

    def archive(self, skill_id: str, by: str = "admin") -> bool:
        return self._decide(skill_id, "archived", by)

    def _decide(self, skill_id: str, status: str, by: str) -> bool:
        sk = self._mem.get(skill_id)
        if not sk or sk.status != "proposed":
            return False
        sk.status = status
        sk.decided_at = time.time()
        sk.decided_by = by
        if self._db_enabled:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute(
                        "UPDATE skill_assets SET status=?, decided_at=?, decided_by=? WHERE skill_id=?",
                        (status, sk.decided_at, by, skill_id),
                    )
            except Exception:  # noqa: BLE001
                pass
        return True

    def lifecycle_gc(self, ttl_days: int = PROPOSED_TTL_DAYS) -> int:
        """归档超过 TTL 的 proposed 草稿（记忆生命周期收敛）。返回归档条数。"""
        cutoff = time.time() - ttl_days * 86400
        archived = 0
        for sk in list(self._mem.values()):
            if sk.status == "proposed" and sk.created_at < cutoff:
                if self._decide(sk.skill_id, "archived", "lifecycle_gc"):
                    archived += 1
        return archived

    def list_skills(self, status: Optional[str] = None, tenant: Optional[str] = None,
                    industry_key: Optional[str] = None) -> List[SkillAsset]:
        out = list(self._mem.values())
        if status:
            out = [s for s in out if s.status == status]
        if tenant:
            out = [s for s in out if s.tenant == tenant]
        if industry_key:
            out = [s for s in out if s.industry_key == industry_key]
        return sorted(out, key=lambda s: s.created_at, reverse=True)

    def get(self, skill_id: str) -> Optional[SkillAsset]:
        return self._mem.get(skill_id)

    def stats(self) -> Dict[str, Any]:
        from collections import Counter

        return {
            "total": len(self._mem),
            "by_status": dict(Counter(s.status for s in self._mem.values())),
            "approved": sum(1 for s in self._mem.values() if s.status == "approved"),
        }


# 进程级单例（与 evolution_loop 单例同生命周期）
skill_asset_store = SkillAssetStore()
