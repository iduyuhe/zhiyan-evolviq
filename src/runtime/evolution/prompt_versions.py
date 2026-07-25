"""P2-2 Prompt 版本化管理——版本化 + 人工审批门 + 热替换 + 一键回滚。

核心安全约束：候选 prompt（proposed）**绝不自动应用**。必须人工 approve → apply。
apply 会热替换 live Agent 单例的 `system_prompt` 属性（若 Agent 暴露该属性），
并记录上一版内容用于回滚。事实锚点铁律：只换指令文本，绝不改写业务数字。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from src.runtime.agent.router import get_agent

logger = logging.getLogger(__name__)


class PromptVersionStore:
    """Prompt 版本存储——内存快读 + 异步落库（重启回灌）。"""

    def __init__(self):
        self._versions: list[dict] = []
        self._sink: Optional[Callable[..., Awaitable[None]]] = None
        self._active: dict[str, str] = {}            # agent -> active version id
        self._applied_stack: dict[str, list[str]] = {}  # agent -> [version_id]，供回滚
        self._snapshot: dict[str, str] = {}          # agent -> 上一版 system_prompt 内容

    # ---------- 落库 ----------
    def attach_sink(self, coro_fn) -> None:
        self._sink = coro_fn

    def _persist(self, rec: dict) -> None:
        if self._sink is None:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._sink(
                    rec["tenant_id"], rec["agent"], rec["version"], rec["content"],
                    rec.get("parent_version"), rec["status"],
                    rec.get("proposer", "llm"), rec.get("note", ""),
                )
            )
        except RuntimeError:
            pass

    # ---------- 版本号 ----------
    def _next_version(self, agent: str) -> int:
        vs = [v["version"] for v in self._versions if v["agent"] == agent]
        return (max(vs) + 1) if vs else 1

    # ---------- 写：propose / approve / apply / rollback ----------
    def propose(
        self, tenant_id: str, agent: str, content: str,
        parent_version: Optional[int] = None, proposer: str = "llm", note: str = "",
    ) -> dict:
        rec = {
            "id": f"pv-{uuid.uuid4().hex[:12]}",
            "tenant_id": tenant_id,
            "agent": agent,
            "version": self._next_version(agent),
            "content": content,
            "parent_version": parent_version,
            "status": "proposed",
            "proposer": proposer,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "applied_at": None,
        }
        self._versions.append(rec)
        self._persist(rec)
        logger.info(f"🧬 Prompt 候选已生成 [{proposer}] {agent} v{rec['version']}（待人工审批）")
        return rec

    def get(self, vid: str) -> Optional[dict]:
        return next((v for v in self._versions if v["id"] == vid), None)

    def approve(self, vid: str) -> dict:
        v = self.get(vid)
        if not v:
            raise KeyError(f"版本不存在: {vid}")
        v["status"] = "approved"
        return v

    def apply(self, vid: str) -> dict:
        """人工确认应用某版本：热替换 live Agent 单例的 system_prompt，并记录回滚点。"""
        v = self.get(vid)
        if not v:
            raise KeyError(f"版本不存在: {vid}")
        agent = v["agent"]

        # 当前 active 退为 approved（不再 active）
        prev_id = self._active.get(agent)
        if prev_id and prev_id != vid:
            prev = self.get(prev_id)
            if prev:
                prev["status"] = "approved"

        # 热替换 live 单例
        old_content = None
        try:
            agent_obj = get_agent(agent)
            if agent_obj is not None and hasattr(agent_obj, "system_prompt"):
                old_content = agent_obj.system_prompt
                agent_obj.system_prompt = v["content"]
        except Exception as e:
            logger.warning(f"⚠️ 热替换 prompt 失败（仅记录版本，不影响应用）：{e}")

        if old_content is not None:
            self._snapshot[agent] = old_content
            self._applied_stack.setdefault(agent, []).append(vid)

        v["status"] = "active"
        v["applied_at"] = datetime.now(timezone.utc).isoformat()
        self._active[agent] = vid
        logger.info(f"✅ Prompt 已应用 {agent} → v{v['version']}（热替换 live 单例）")
        return v

    def rollback(self, agent: str) -> dict:
        """一键回滚该 Agent 最近一次 prompt 应用，恢复上一版内容。"""
        stack = self._applied_stack.get(agent, [])
        if not stack:
            return {"status": "no_change", "agent": agent}
        vid = stack.pop()
        v = self.get(vid)
        prev_content = self._snapshot.get(agent)
        restored = None
        try:
            agent_obj = get_agent(agent)
            if agent_obj is not None and hasattr(agent_obj, "system_prompt") and prev_content is not None:
                agent_obj.system_prompt = prev_content
                restored = prev_content
        except Exception as e:
            logger.warning(f"⚠️ 回滚热替换失败：{e}")
        if v:
            v["status"] = "approved"
        if stack:
            self._active[agent] = stack[-1]
            pv = self.get(stack[-1])
            if pv:
                pv["status"] = "active"
        else:
            self._active.pop(agent, None)
        logger.info(f"↩️ Prompt 已回滚 {agent}（还原至 v{v['version'] if v else '?'})")
        return {
            "status": "rolled_back",
            "agent": agent,
            "restored_version": vid,
            "restored_content": restored,
        }

    # ---------- 读 ----------
    def list_versions(self, agent: str, tenant: Optional[str] = None) -> list[dict]:
        recs = [v for v in self._versions if v["agent"] == agent]
        if tenant not in (None, "all"):
            recs = [r for r in recs if r.get("tenant_id") == tenant]
        return list(sorted(recs, key=lambda x: x["version"]))

    def active_version(self, agent: str, tenant: Optional[str] = None) -> Optional[dict]:
        aid = self._active.get(agent)
        if not aid:
            return None
        v = self.get(aid)
        if v and (tenant in (None, "all") or v.get("tenant_id") == tenant):
            return v
        return None

    def current_prompt(self, agent: str) -> str:
        """读 live Agent 单例当前生效的 system_prompt（用于复盘时作为 parent）。"""
        try:
            obj = get_agent(agent)
            if obj is not None and hasattr(obj, "system_prompt"):
                return obj.system_prompt
        except Exception:
            pass
        return ""

    # ---------- 回灌 ----------
    async def hydrate(self, limit: int = 500) -> int:
        from src.runtime.persistence import load_prompt_versions

        rows = await load_prompt_versions(limit=limit)
        self._versions = rows
        self._active = {}
        for v in self._versions:
            if v.get("status") == "active":
                self._active[v["agent"]] = v["id"]
        logger.info(f"🧬 Prompt 版本回灌 {len(self._versions)} 条（跨重启累积）")
        return len(self._versions)


# 全局单例
prompt_versions = PromptVersionStore()
