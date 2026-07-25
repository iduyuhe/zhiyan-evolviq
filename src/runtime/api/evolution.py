"""P2 自进化 API——Prompt 自反思/版本化/审批、KG 事实自更新、偏好校准。

所有"变更类"操作均设**人工审批门**：候选 prompt / KG 事实先进入 draft/proposed，
必须显式 approve 才生效。绝不自动应用（安全铁律）。
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.runtime.evolution import prompt_versions, kg_facts, reflection, failure_store, preference_learning
from src.runtime.api.deps import get_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evolution", tags=["evolution"])


# ---------- P2-3 自反思 + P2-2 版本化 ----------
class ReflectRequest(BaseModel):
    agent: str
    note: str = ""


@router.post("/reflect")
async def reflect(req: ReflectRequest, tenant: str = Depends(get_tenant)):
    """复盘某 Agent 失败案例 → 生成候选 prompt（LLM/启发式）→ 存为 proposed 版本（不自动应用）。"""
    try:
        from src.runtime.agent.router import AGENT_REGISTRY
        if req.agent not in AGENT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"未知 Agent: {req.agent}")
    except ImportError:
        pass
    cases = failure_store.collect_failure_cases(req.agent)
    current = prompt_versions.current_prompt(req.agent)
    res = await reflection.reflect(req.agent, cases, current)
    parent = prompt_versions.active_version(req.agent, tenant=tenant)
    rec = prompt_versions.propose(
        tenant_id=tenant, agent=req.agent, content=res.proposed_prompt,
        parent_version=parent["version"] if parent else None,
        proposer=res.source, note=req.note or res.rationale,
    )
    return {
        "agent": req.agent,
        "failure_cases": len(cases),
        "source": res.source,
        "version_id": rec["id"],
        "version": rec["version"],
        "status": rec["status"],
        "rationale": res.rationale,
        "proposed_prompt": res.proposed_prompt,
    }


@router.get("/failure-cases/{agent}")
async def failure_cases(agent: str, limit: int = 12):
    """查看某 Agent 的失败案例（透明化自进化的养料）。"""
    return {"agent": agent, "cases": [c.__dict__ for c in failure_store.collect_failure_cases(agent, limit=limit)]}


@router.get("/prompt-versions/{agent}")
async def list_versions(agent: str, tenant: str = Depends(get_tenant)):
    """列出某 Agent 的全部 Prompt 版本 + 当前 active。"""
    return {
        "agent": agent,
        "versions": prompt_versions.list_versions(agent, tenant=tenant),
        "active": prompt_versions.active_version(agent, tenant=tenant),
    }


@router.post("/prompt-versions/{vid}/approve")
async def approve_version(vid: str):
    """人工审批通过某候选 prompt 版本（approved，尚未应用）。"""
    try:
        v = prompt_versions.approve(vid)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "approved", "version": v}


@router.post("/prompt-versions/{vid}/apply")
async def apply_version(vid: str):
    """人工确认应用某版本：热替换 live Agent 的 system_prompt。"""
    try:
        v = prompt_versions.apply(vid)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "applied", "version": v}


@router.post("/prompt-versions/{agent}/rollback")
async def rollback_version(agent: str):
    """一键回滚该 Agent 最近一次 prompt 应用，恢复上一版内容。"""
    return prompt_versions.rollback(agent)


@router.get("/prompt-versions/{agent}/active")
async def active_prompt(agent: str, tenant: str = Depends(get_tenant)):
    """查看当前生效的 prompt 版本 + live 单例实际内容。"""
    v = prompt_versions.active_version(agent, tenant=tenant)
    return {"agent": agent, "active": v, "current_live_prompt": prompt_versions.current_prompt(agent)}


# ---------- P2-4 RAG 知识自更新 ----------
class KgFactRequest(BaseModel):
    agent: str
    subject: str
    predicate: str
    object: str
    source: str = ""
    confidence: float = 0.8
    note: str = ""


@router.post("/kg-facts/propose")
async def propose_fact(req: KgFactRequest, tenant: str = Depends(get_tenant)):
    """提议一条知识图谱事实（draft，待审批）。"""
    rec = kg_facts.propose(
        tenant, req.agent, req.subject, req.predicate, req.object,
        req.source, req.confidence, req.note,
    )
    return {"status": "draft", "proposal": rec}


@router.get("/kg-facts")
async def list_facts(agent: Optional[str] = None, tenant: str = Depends(get_tenant)):
    """列出 KG 事实提议。"""
    return {"proposals": kg_facts.list_proposals(agent=agent, tenant=tenant)}


@router.post("/kg-facts/{kid}/approve")
async def approve_fact(kid: str, tenant: str = Depends(get_tenant)):
    """人工审批通过 → upsert 进知识图谱（事实锚点，绝不改写业务数字）。"""
    try:
        p = await kg_facts.approve(kid, tenant_id=tenant)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "approved", "proposal": p}


# ---------- P2-5 在线偏好学习 lite ----------
@router.get("/preference/{agent}")
async def preference(agent: str):
    """该 Agent 的在线偏好校准信号（仅供驱动其它模块，不直接改业务数字）。"""
    return preference_learning.preference_calibration(agent)
