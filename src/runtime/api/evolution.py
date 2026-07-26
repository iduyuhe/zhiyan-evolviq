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
from src.runtime.evolution.ontology import ontology as ontology_store
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


# ---------- v23.0 广样本反思 ----------

@router.post("/reflect-broad")
async def reflect_broad(req: ReflectRequest, tenant: str = Depends(get_tenant)):
    """广样本反思：融合失败/成功/后果校验/KG 验证四个维度 → 生成候选 prompt。"""
    try:
        from src.runtime.agent.router import AGENT_REGISTRY
        if req.agent not in AGENT_REGISTRY:
            raise HTTPException(status_code=404, detail=f"未知 Agent: {req.agent}")
    except ImportError:
        pass

    # 采集四个维度的样本
    failure_cases = failure_store.collect_failure_cases(req.agent)
    from src.runtime.experience import experience
    success_cases = experience.get_preferences(req.agent)
    from src.runtime.consequence import consequence
    con_cases = consequence.query(agent=req.agent)
    kg_validated = [p for p in kg_facts.list_proposals(agent=f"tacit:{req.agent}" if req.agent else None)
                    if p.get("status") in ("validated", "approved")]

    current = prompt_versions.current_prompt(req.agent)
    res = await reflection.reflect_broad(
        agent=req.agent, current_prompt=current,
        failure_cases=failure_cases,
        success_cases=success_cases,
        consequence_cases=con_cases,
        kg_validated=kg_validated,
    )
    parent = prompt_versions.active_version(req.agent, tenant=tenant)
    rec = prompt_versions.propose(
        tenant_id=tenant, agent=req.agent, content=res.proposed_prompt,
        parent_version=parent["version"] if parent else None,
        proposer=res.source, note=req.note or res.rationale,
    )
    return {
        "agent": req.agent,
        "samples": {
            "failure_cases": len(failure_cases),
            "success_cases": len(success_cases),
            "consequence_cases": len(con_cases),
            "kg_validated": len(kg_validated),
        },
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


class RejectRequest(BaseModel):
    reason: str = ""


@router.post("/kg-facts/{kid}/reject")
async def reject_fact(kid: str, req: RejectRequest):
    """驳回一条 KG 事实提议（不写入图谱），自动记录虚拟后果。"""
    try:
        p = kg_facts.reject(kid, reason=req.reason)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "rejected", "proposal": p}


# ---------- P2-5 在线偏好学习 lite ----------
@router.get("/preference/{agent}")
async def preference(agent: str):
    """该 Agent 的在线偏好校准信号（仅供驱动其它模块，不直接改业务数字）。"""
    return preference_learning.preference_calibration(agent)


# ---------- v25.0 工业本体自生长 ----------

@router.get("/ontology/schema")
async def ontology_schema():
    """当前本体 schema 一览（实体类型 + 关系类型 + 汇总）。"""
    return {
        "summary": ontology_store.schema_summary(),
        "entity_types": [{"name": e.name, "description": e.description, "status": e.status, "source": e.source}
                         for e in ontology_store.entity_types()],
        "relationship_types": [{"name": e.name, "description": e.description, "status": e.status, "source": e.source}
                               for e in ontology_store.relationship_types()],
    }


@router.get("/ontology/discover")
async def ontology_discover():
    """从 KG 事实提议中扫描潜在的新实体类型和关系类型候选。"""
    return ontology_store.discover()


class OntologyExtensionRequest(BaseModel):
    kind: str  # "entity_type" | "relationship_type"
    name: str
    description: str = ""


@router.post("/ontology/extensions")
async def propose_ontology_extension(req: OntologyExtensionRequest):
    """提议一条本体扩展（实体类型或关系类型）→ 存为 proposed 待审批。"""
    try:
        prop = ontology_store.propose_extension(req.kind, req.name, req.description)
        return {"status": "proposed", "proposal": prop}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/ontology/extensions/{proposal_id}/approve")
async def approve_ontology_extension(proposal_id: str):
    """人工审批通过一条本体扩展提议。"""
    try:
        prop = ontology_store.approve_extension(proposal_id)
        return {"status": "approved", "proposal": prop}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
