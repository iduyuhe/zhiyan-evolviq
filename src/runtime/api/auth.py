"""授权边界配置API——AI原生核心接口

提供授权边界的 CRUD，以及按Agent查询当前生效边界。
边界数据由 AuthorizationEngine 统一内存管理。

对应策划方案 模块四「授权边界配置」(MVP必修)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.runtime.core.authorization import authorization
from src.runtime.models.authorization import AuthBoundary, AuthBoundaryCreate

router = APIRouter(prefix="/auth", tags=["authorization"])


class UpdateBoundaryRequest(BaseModel):
    name: str | None = None
    allowed_categories: list[str] | None = None
    price_tolerance_pct: float | None = None
    max_lock_qty: int | None = None
    confidence_threshold: float | None = None
    auto_execute_actions: list[str] | None = None
    require_approval_actions: list[str] | None = None
    max_daily_autonomous: int | None = None
    enabled: bool | None = None


@router.get("/boundaries")
async def list_boundaries():
    """列出所有授权边界"""
    boundaries = authorization.list()
    return {
        "boundaries": [b.model_dump() for b in boundaries],
        "total": len(boundaries),
    }


@router.get("/boundaries/{boundary_id}")
async def get_boundary(boundary_id: str):
    b = authorization.get(boundary_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return b.model_dump()


@router.get("/boundaries/agent/{agent}")
async def get_agent_boundary(agent: str):
    """取某Agent当前生效边界"""
    b = authorization.get_for_agent(agent)
    if not b:
        return {"boundary": None, "agent": agent}
    return {"boundary": b.model_dump(), "agent": agent}


@router.post("/boundaries")
async def create_boundary(req: AuthBoundaryCreate):
    """创建授权边界"""
    b = authorization.create(req)
    return {"id": b.id, "name": b.name, "status": "created", "boundary": b.model_dump()}


@router.put("/boundaries/{boundary_id}")
async def update_boundary(boundary_id: str, req: AuthBoundaryCreate):
    """全量更新授权边界"""
    b = authorization.update(boundary_id, req)
    if not b:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return {"id": boundary_id, "status": "updated", "boundary": b.model_dump()}


@router.patch("/boundaries/{boundary_id}")
async def patch_boundary(boundary_id: str, req: UpdateBoundaryRequest):
    """局部更新授权边界"""
    cur = authorization.get(boundary_id)
    if not cur:
        raise HTTPException(status_code=404, detail="Boundary not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    from src.runtime.models.authorization import AuthBoundaryCreate
    merged = cur.model_dump()
    merged.update(updates)
    merged.pop("id", None)
    merged.pop("created_at", None)
    merged.pop("updated_at", None)
    updated = authorization.update(boundary_id, AuthBoundaryCreate(**merged))
    return {"id": boundary_id, "status": "patched", "boundary": updated.model_dump()}


@router.delete("/boundaries/{boundary_id}")
async def delete_boundary(boundary_id: str):
    ok = authorization.delete(boundary_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return {"id": boundary_id, "status": "deleted"}
