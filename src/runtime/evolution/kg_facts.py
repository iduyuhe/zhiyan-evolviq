"""P2-4 RAG 知识自更新——从结构化产出抽取事实，提议写入知识图谱（人工审批）。

事实提议经人工 approve 后 upsert 进 Neo4j 知识图谱（Entity 节点 + 关系边），
并落一条 Insight，便于后续 BaseAgent.recall 读回，提升 RAG 检索质量。
事实锚点铁律：仅写实体/关系，绝不改写业务数字。韧性降级：Neo4j 不可达走内存图。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class KgFactStore:
    def __init__(self):
        self._proposals: list[dict] = []
        self._sink: Optional[Callable[..., Awaitable[None]]] = None

    def attach_sink(self, coro_fn) -> None:
        self._sink = coro_fn

    def _persist(self, rec: dict) -> None:
        if self._sink is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._sink(
                    rec["tenant_id"], rec["agent"], rec["subject"], rec["predicate"],
                    rec["object_val"], rec.get("source", ""), rec.get("confidence", 0.8),
                    rec.get("note", ""),
                )
            )
        except RuntimeError:
            pass

    def propose(
        self, tenant_id: str, agent: str, subject: str, predicate: str, object_val: str,
        source: str = "", confidence: float = 0.8, note: str = "",
    ) -> dict:
        rec = {
            "id": f"kf-{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant_id,
            "agent": agent,
            "subject": subject,
            "predicate": predicate,
            "object_val": object_val,
            "source": source,
            "confidence": float(confidence),
            "status": "draft",
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._proposals.append(rec)
        self._persist(rec)
        logger.info(f"🕸️ KG 事实提议已生成 {agent}: {subject} —{predicate}→ {object_val}（待审批）")
        return rec

    def get(self, kid: str) -> Optional[dict]:
        return next((p for p in self._proposals if p["id"] == kid), None)

    async def approve(self, kid: str, tenant_id: str = "default") -> dict:
        """人工审批通过 → upsert 进知识图谱 + 落 Insight。"""
        p = self.get(kid)
        if not p:
            raise KeyError(f"事实提议不存在: {kid}")
        p["status"] = "approved"
        try:
            from src.common import neo4j_client as neo

            await neo.merge_node("Entity", f"ENTITY:{p['subject']}", {"name": p["subject"]})
            await neo.merge_node("Entity", f"ENTITY:{p['object_val']}", {"name": p["object_val"]})
            await neo.merge_edge(
                f"ENTITY:{p['subject']}", f"ENTITY:{p['object_val']}", p["predicate"],
                {
                    "source": p.get("source", ""),
                    "confidence": p.get("confidence", 0.8),
                    "tenant": tenant_id,
                    "approved_at": p["created_at"],
                },
            )
            # 落一条 Insight，便于 recall 读回（复用 P0 经验记忆链路）
            nid = f"INSIGHT:{uuid.uuid4().hex[:12]}"
            await neo.merge_node("Insight", nid, {
                "source": "kg_self_update",
                "agent": p["agent"],
                "text": f"{p['subject']} {p['predicate']} {p['object_val']}"[:500],
                "tenant": tenant_id,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"🕸️ KG 事实已写入：{p['subject']} —{p['predicate']}→ {p['object_val']}")
        except Exception as e:
            logger.warning(f"⚠️ KG 事实 upsert 失败（不破管）：{e}")
        return p

    def list_proposals(self, agent: Optional[str] = None, tenant: Optional[str] = None) -> list[dict]:
        recs = self._proposals
        if agent:
            recs = [r for r in recs if r["agent"] == agent]
        if tenant not in (None, "all"):
            recs = [r for r in recs if r.get("tenant_id") == tenant]
        return list(sorted(recs, key=lambda x: x["created_at"], reverse=True))

    async def hydrate(self, limit: int = 500) -> int:
        from src.runtime.persistence import load_kg_fact_proposals

        rows = await load_kg_fact_proposals(limit=limit)
        self._proposals = rows
        logger.info(f"🧬 KG 事实提议回灌 {len(self._proposals)} 条（跨重启累积）")
        return len(self._proposals)

    # ---------- v22 蓝弧：后果校验 → 置信度调整 + 自动纠错（自进化燃料） ----------

    def validate_fact(self, kid: str, ok: bool, evidence: dict | None = None) -> dict | None:
        """事实后果校验：基于执行后果回流，修正符号置信度。

        - ok=True: 提升置信度(+0.10)，标记 validated
        - ok=False: 降低置信度(-0.15)；若低于阈值则提议纠错 draft（自进化燃料）
        返回修正后的事实 dict，或 None（kid 不存在）。
        """
        p = self.get(kid)
        if p is None:
            logger.warning(f"⚠️ 事实校验跳过：kid={kid} 不存在")
            return None

        if ok:
            p["confidence"] = min(0.99, float(p.get("confidence", 0.8)) + 0.10)
            p["status"] = "validated"
        else:
            p["confidence"] = max(0.01, float(p.get("confidence", 0.8)) - 0.15)
            p["status"] = "needs_review"
            # 低于阈值 → 提议纠错 draft（自进化燃料）
            if p["confidence"] < 0.30:
                corrected = self._propose_correction(p, evidence)
                logger.info(
                    f"🕸️ 自动纠错已提议：{p['subject']} ~{p['predicate']}→ {p['object_val']}"
                    f"（修正原事实 {p['id']}）"
                )
                return corrected

        p["validate_evidence"] = json.dumps(evidence or {}, ensure_ascii=False)[:500]
        logger.info(f"🔄 事实后果校验 [{'✓' if ok else '✗'}] {p['subject']} {p['predicate']} {p['object_val']}")
        return p

    def _propose_correction(self, original: dict, evidence: dict | None) -> dict:
        """基于被后果否定的旧事实，提议一条纠错新事实（自进化燃料）。

        使用否定谓词（~原谓词）标记为修正关系，带有 corrects 字段指向原事实。
        待人类审批门 approve 后进入图谱。
        """
        corrected = {
            "id": f"kf-{uuid.uuid4().hex[:12]}",
            "tenant_id": original.get("tenant_id", "default"),
            "agent": f"consequence:{original.get('agent', 'unknown')}",
            "subject": original["subject"],
            "predicate": f"~{original['predicate']}",
            "object_val": original["object_val"],
            "source": f"auto_correction:{original.get('id', '')}",
            "confidence": 0.5,
            "status": "draft",
            "note": f"自动纠错提议：基于后果校验校验（原事实 {original.get('id', '')}）",
            "note_evidence": json.dumps(evidence or {}, ensure_ascii=False)[:500],
            "corrects": original["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._proposals.append(corrected)
        self._persist(corrected)
        return corrected


# 全局单例
kg_facts = KgFactStore()
