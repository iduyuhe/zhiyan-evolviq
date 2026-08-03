"""刀4·迭代1 评估信号采集（自我进化闭环第一环）。

自我进化闭环 = 评估信号（执行结果 + 人工反馈）→ 资产更新（记忆 / 图谱 / 技能 / 阈值）。
本迭代只做「采集 + 归一 + 持久化 + 对外匿名视图」，资产更新回灌留待迭代2。

信号来源（挖存量，绝不新建）：
- 执行结果：src.runtime.consequence.ConsequenceTracker（蓝弧闭环已沉淀）
- 人工反馈：src.runtime.feedback_store.FeedbackStore（共生进化环，已脱敏门）

纪律（docs/TECHNICAL_DELIVERY_SCOPE.md §3/§6）：
- 零真名：信号 payload 只含 agent / case_id / action_id / 匿名反馈文本；
  命中 LEAK_TOKENS 的反馈信号一律丢弃（绝不外传企业真名 / PII）。
- 挖存量：仅编排既有模块，不新增案例 / 行业 / agent / REST 端点。
- 延迟部署：纯后端结构化，未接入运行时 import，符合基线 §4。
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.compliance_reviewer.agent import LEAK_TOKENS
from src.runtime.feedback_store import desensitize

# 资产目标（迭代2 回灌通道的路由键；本迭代仅作标记）
ASSET_MEMORY = "memory"
ASSET_KG = "kg"
ASSET_SKILL = "skill"
ASSET_THRESHOLD = "threshold"


@dataclass
class EvaluationSignal:
    """一条归一化的评估信号（零真名，可安全进入资产更新通道）。"""

    signal_id: str
    source: str            # execution / feedback
    signal_kind: str       # validated / contradicted / like / dislike / idea
    asset_target: str      # memory / kg / skill / threshold（路由提示）
    agent: str             # 框架 agent 名 或 "user"（非企业真名）
    industry_key: str = ""
    case_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    linked_kind: str = ""  # consequence / feedback
    linked_id: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "source": self.source,
            "signal_kind": self.signal_kind,
            "asset_target": self.asset_target,
            "agent": self.agent,
            "industry_key": self.industry_key,
            "case_id": self.case_id,
            "payload": self.payload,
            "linked_kind": self.linked_kind,
            "linked_id": self.linked_id,
            "created_at": self.created_at,
        }


def _contains_leak(blob: str) -> List[str]:
    """返回 blob 中命中的真实锚定 token（零真名铁律的判定函数）。"""
    return [t for t in LEAK_TOKENS if t in blob]


def _derive_execution_signal(rec: Dict[str, Any]) -> Optional[EvaluationSignal]:
    """从一条执行后果记录派生评估信号（零真名：不携带 predicted/actual 业务数字）。"""
    match = bool(rec.get("match"))
    detail = rec.get("match_detail", {}) or {}
    matched = detail.get("matched_keys")
    total = detail.get("total_keys")
    kind = "validated" if match else "contradicted"
    # 资产路由：匹配 → 阈值信任上升；不匹配 → 技能复盘
    asset_target = ASSET_THRESHOLD if match else ASSET_SKILL
    sig = EvaluationSignal(
        signal_id=f"ev-{uuid.uuid4().hex[:12]}",
        source="execution",
        signal_kind=kind,
        asset_target=asset_target,
        agent=rec.get("agent", "unknown"),
        payload={
            "match": match,
            "matched_keys": matched,
            "total_keys": total,
        },
        linked_kind="consequence",
        linked_id=rec.get("id", ""),
    )
    # 若执行后果关联 KG 事实，改投 kg 通道（不匹配时下调事实置信）
    if rec.get("linked_fact_id"):
        sig.asset_target = ASSET_KG if not match else asset_target
        sig.payload["linked_fact_id"] = rec["linked_fact_id"]
    return sig


def _derive_feedback_signal(fb: Dict[str, Any]) -> Optional[EvaluationSignal]:
    """从一条反馈派生评估信号。

    零真名：仅用脱敏文本；含 LEAK_TOKENS 残留的信号直接丢弃（防御性，绝不外传真名/PII）。
    """
    ft = fb.get("feedback_type", "")
    if ft not in ("like", "dislike", "idea"):
        return None
    raw_text = fb.get("desensitized_text") or fb.get("text") or ""
    clean = desensitize(raw_text)
    if _contains_leak(clean):
        return None  # 含真名/PII 残留，丢弃
    asset_target = {
        "like": ASSET_MEMORY,
        "dislike": ASSET_THRESHOLD,
        "idea": ASSET_SKILL,
    }[ft]
    sig = EvaluationSignal(
        signal_id=f"ev-{uuid.uuid4().hex[:12]}",
        source="feedback",
        signal_kind=ft,
        asset_target=asset_target,
        agent="user",
        case_id=fb.get("target_id", ""),
        payload={
            "feedback_type": ft,
            "target_kind": fb.get("target_kind", ""),
            "text": clean[:280],
        },
        linked_kind="feedback",
        linked_id=fb.get("id", ""),
    )
    return sig


class EvolutionLoop:
    """评估信号采集器（自我进化闭环第一环）。

    从执行后果 + 人工反馈两个存量源采集、归一、去重、持久化评估信号，
    供迭代2 的资产更新通道消费。纯后端、零真名。
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.environ.get("ZHIYAN_EVOLUTION_DB", "./zhiyan_evolution.db")
        self._db_enabled = self._db_path.lower() != "disabled"
        self._signals: List[EvaluationSignal] = []
        self._seen: set = set()
        if self._db_enabled:
            self._init_db()
            self._load()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS eval_signals (
                        signal_id TEXT PRIMARY KEY,
                        source TEXT, signal_kind TEXT, asset_target TEXT,
                        agent TEXT, payload TEXT, linked_kind TEXT, linked_id TEXT,
                        created_at REAL
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
                    "SELECT signal_id,source,signal_kind,asset_target,agent,"
                    "payload,linked_kind,linked_id,created_at FROM eval_signals"
                ).fetchall()
            for r in rows:
                sig = EvaluationSignal(
                    r[0], r[1], r[2], r[3], r[4],
                    payload=json.loads(r[5]), linked_kind=r[6],
                    linked_id=r[7], created_at=r[8],
                )
                self._signals.append(sig)
                self._seen.add(f"{sig.linked_kind}:{sig.linked_id}")
        except Exception:  # noqa: BLE001
            pass

    def collect(self, consequence_tracker=None, feedback_store=None,
                limit: int = 100) -> int:
        """从两个存量源采集新评估信号，去重后入库。返回新增条数。"""
        from src.runtime.consequence import consequence as _default_cons
        from src.runtime.feedback_store import feedback_store as _default_fb

        ctracker = consequence_tracker or _default_cons
        fstore = feedback_store or _default_fb

        added = 0

        # 1) 执行后果
        try:
            recs = ctracker.query(agent=None, limit=limit)
        except Exception:  # noqa: BLE001
            recs = []
        for rec in recs:
            key = f"consequence:{rec.get('id', '')}"
            if key in self._seen:
                continue
            sig = _derive_execution_signal(rec)
            if sig is None:
                continue
            self._ingest(sig)
            added += 1

        # 2) 人工反馈
        try:
            fbs = fstore.list_all()
        except Exception:  # noqa: BLE001
            fbs = []
        for fb in fbs:
            key = f"feedback:{fb.get('id', '')}"
            if key in self._seen:
                continue
            sig = _derive_feedback_signal(fb)
            if sig is None:
                continue
            self._ingest(sig)
            added += 1

        return added

    def _ingest(self, sig: EvaluationSignal) -> None:
        self._signals.append(sig)
        self._seen.add(f"{sig.linked_kind}:{sig.linked_id}")
        if self._db_enabled:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO eval_signals VALUES (?,?,?,?,?,?,?,?,?)",
                        (sig.signal_id, sig.source, sig.signal_kind, sig.asset_target,
                         sig.agent, json.dumps(sig.payload, ensure_ascii=False),
                         sig.linked_kind, sig.linked_id, sig.created_at),
                    )
            except Exception:  # noqa: BLE001
                pass

    def signals(self, asset_target: Optional[str] = None,
                limit: int = 50) -> List[EvaluationSignal]:
        out = self._signals
        if asset_target:
            out = [s for s in out if s.asset_target == asset_target]
        return sorted(out, key=lambda s: s.created_at, reverse=True)[:limit]

    def stats(self) -> Dict[str, Any]:
        return {
            "total": len(self._signals),
            "by_source": dict(Counter(s.source for s in self._signals)),
            "by_kind": dict(Counter(s.signal_kind for s in self._signals)),
            "by_asset_target": dict(Counter(s.asset_target for s in self._signals)),
        }


# 进程级单例
evolution_loop = EvolutionLoop()
