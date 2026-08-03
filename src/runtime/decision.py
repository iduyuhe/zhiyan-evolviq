"""决策引擎 + 决策事件（刀3 迭代1）。

把分散在 25 个 Agent.analyze 内的"决策"抽象为统一枢纽层（认知→执行的枢纽）：
- DecisionProposal：候选动作 + 多目标权衡 + 约束校验（治理前置）+ 证据链（引用 case_id 零真名）。
- DecisionStore：决策事件持久化（SQLite，韧性降级纯内存），证据可追溯、可复盘。

设计纪律（范围基线 docs/TECHNICAL_DELIVERY_SCOPE.md §3/§6）：
- 零真名：context/evidence 只含 case_id / industry_key / node_category / source / agent，
  绝不碰 real_anchor；LEAK_TOKENS 断言同 compliance_reviewer。
- 挖存量：复用既有案例 / 知识图谱元信息，不新建案例 / 行业 / agent；不引图库重设施。
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

# 多目标权衡默认维度（开放获取，可后续迭代扩展）
TRADEOFF_OBJECTIVES = ("成本", "交期", "风险", "质量", "合规")


@dataclass
class ConstraintCheck:
    name: str
    passed: bool
    reason: str = ""


@dataclass
class EvidenceLink:
    kind: str       # case / kg_node / source / agent / rule
    ref: str        # case_id / node id / source / agent name（零真名）
    note: str = ""


@dataclass
class CandidateAction:
    action_name: str
    expected_effect: str
    score: float = 0.0


@dataclass
class DecisionProposal:
    proposal_id: str
    title: str
    context: Dict[str, Any]
    candidate_actions: List[CandidateAction]
    tradeoffs: Dict[str, Dict[str, float]]   # objective -> {action_name: score}
    constraints: List[ConstraintCheck]
    evidence: List[EvidenceLink]
    recommended_action: Optional[str] = None
    decided_action: Optional[str] = None
    status: str = "proposed"   # proposed / decided / executed / rejected
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "title": self.title,
            "context": self.context,
            "candidate_actions": [vars(c) for c in self.candidate_actions],
            "tradeoffs": self.tradeoffs,
            "constraints": [vars(c) for c in self.constraints],
            "evidence": [vars(e) for e in self.evidence],
            "recommended_action": self.recommended_action,
            "decided_action": self.decided_action,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionProposal":
        return cls(
            proposal_id=d["proposal_id"], title=d["title"], context=d.get("context", {}),
            candidate_actions=[CandidateAction(**c) for c in d.get("candidate_actions", [])],
            tradeoffs=d.get("tradeoffs", {}),
            constraints=[ConstraintCheck(**c) for c in d.get("constraints", [])],
            evidence=[EvidenceLink(**e) for e in d.get("evidence", [])],
            recommended_action=d.get("recommended_action"),
            decided_action=d.get("decided_action"),
            status=d.get("status", "proposed"),
            created_at=d.get("created_at", time.time()),
        )


class DecisionStore:
    """决策事件持久化（SQLite，韧性降级纯内存；复用 writeback 同源韧性铁律）。"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or os.environ.get("ZHIYAN_DECISION_DB", "./zhiyan_decision.db")
        self._db_enabled = self._db_path.lower() != "disabled"
        self._mem: Dict[str, DecisionProposal] = {}
        if self._db_enabled:
            self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS decision_events (
                        proposal_id TEXT PRIMARY KEY,
                        industry_key TEXT,
                        title TEXT,
                        status TEXT,
                        payload TEXT,
                        created_at REAL
                    )"""
                )
        except Exception:  # noqa: BLE001  韧性：SQLite 初始化失败降级纯内存
            self._db_enabled = False

    def save(self, p: DecisionProposal) -> None:
        self._mem[p.proposal_id] = p
        if not self._db_enabled:
            return
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO decision_events VALUES (?,?,?,?,?,?)",
                    (p.proposal_id, p.context.get("industry_key"),
                     p.title, p.status, json.dumps(p.to_dict(), ensure_ascii=False),
                     p.created_at),
                )
        except Exception:  # noqa: BLE001
            pass

    def get(self, proposal_id: str) -> Optional[DecisionProposal]:
        if proposal_id in self._mem:
            return self._mem[proposal_id]
        if not self._db_enabled:
            return None
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT payload FROM decision_events WHERE proposal_id = ?",
                    (proposal_id,)
                ).fetchone()
            if row:
                return DecisionProposal.from_dict(json.loads(row[0]))
        except Exception:  # noqa: BLE001
            return None
        return None

    def list_by_industry(self, industry_key: str) -> List[DecisionProposal]:
        out: List[DecisionProposal] = [
            p for p in self._mem.values() if p.context.get("industry_key") == industry_key
        ]
        if not self._db_enabled:
            return out
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT payload FROM decision_events WHERE industry_key = ? "
                    "ORDER BY created_at",
                    (industry_key,)
                ).fetchall()
            for r in rows:
                p = DecisionProposal.from_dict(json.loads(r[0]))
                if p.proposal_id not in {x.proposal_id for x in out}:
                    out.append(p)
        except Exception:  # noqa: BLE001
            pass
        return out

    def mark_decided(self, proposal_id: str, action: str,
                     actor: str = "human") -> Optional[DecisionProposal]:
        p = self.get(proposal_id)
        if not p:
            return None
        p.decided_action = action
        p.status = "decided"
        p.context = {**p.context, "decided_by": actor, "decided_at": time.time()}
        self.save(p)
        return p

    def mark_executed(self, proposal_id: str) -> Optional[DecisionProposal]:
        p = self.get(proposal_id)
        if not p:
            return None
        p.status = "executed"
        self.save(p)
        return p

    def _all(self) -> List[DecisionProposal]:
        all_p = list(self._mem.values())
        if self._db_enabled:
            try:
                with sqlite3.connect(self._db_path) as conn:
                    rows = conn.execute("SELECT payload FROM decision_events").fetchall()
                for r in rows:
                    p = DecisionProposal.from_dict(json.loads(r[0]))
                    if p.proposal_id not in self._mem:
                        all_p.append(p)
            except Exception:  # noqa: BLE001
                pass
        return all_p

    def stats(self) -> Dict[str, int]:
        return dict(Counter(p.status for p in self._all()))

    def north_star(self) -> Dict[str, Any]:
        """北极星：决策实时化率 = 已执行决策数 / 决策提案总数。

        闭环语义：提案真正被「执行」（落账本/动作完成）即视为实时化；停滞在未决策/
        未执行状态的提案拉低实时化率。MVP 目标 ≥ 40%，稳态目标 ≥ 85%。
        """
        all_p = self._all()
        total = len(all_p)
        executed = sum(1 for p in all_p if p.status == "executed")
        rate = (executed / total) if total else 0.0
        return {
            "total": total,
            "executed": executed,
            "real_time_rate": rate,
            "target_mvp": 0.40,
            "target_steady": 0.85,
        }


def build_proposal(title: str, context: Dict[str, Any],
                   candidate_actions: List[CandidateAction],
                   tradeoffs: Dict[str, Dict[str, float]],
                   constraints: List[ConstraintCheck],
                   evidence: List[EvidenceLink],
                   recommended_action: Optional[str] = None) -> DecisionProposal:
    """构造决策提案（标准结构）。约束不通过时 recommended_action 置空（治理前置）。"""
    passed = all(c.passed for c in constraints)
    rec = recommended_action if (passed and recommended_action) else None
    return DecisionProposal(
        proposal_id=uuid.uuid4().hex[:12], title=title, context=context,
        candidate_actions=candidate_actions, tradeoffs=tradeoffs,
        constraints=constraints, evidence=evidence,
        recommended_action=rec, status="proposed",
    )
