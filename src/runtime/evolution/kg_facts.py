"""P2-4 RAG 知识自更新——从结构化产出抽取事实，提议写入知识图谱（人工审批）。

事实提议经人工 approve 后 upsert 进 Neo4j 知识图谱（Entity 节点 + 关系边），
并落一条 Insight，便于后续 BaseAgent.recall 读回，提升 RAG 检索质量。
事实锚点铁律：仅写实体/关系，绝不改写业务数字。韧性降级：Neo4j 不可达走内存图。
"""

from __future__ import annotations

import asyncio
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


# 全局单例
kg_facts = KgFactStore()
