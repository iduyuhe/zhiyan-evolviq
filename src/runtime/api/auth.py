"""授权边界配置API——AI原生核心接口（多租户版）

提供授权边界的 CRUD，以及按Agent查询当前生效边界。
边界数据按租户隔离：所有操作作用于请求所解析出的租户（X-Tenant-Key）。
未携带密钥 → 默认租户 default。

对应策划方案 模块四「授权边界配置」(MVP必修)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.runtime.core.authorization import authorization
from src.runtime.models.authorization import AuthBoundary, AuthBoundaryCreate
from src.runtime.api.deps import get_tenant

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
async def list_boundaries(tenant: str = Depends(get_tenant)):
    """列出当前租户的全部授权边界"""
    scope = authorization.for_tenant(tenant)
    boundaries = scope.list()
    return {
        "tenant_id": tenant,
        "boundaries": [b.model_dump() for b in boundaries],
        "total": len(boundaries),
    }


@router.get("/boundaries/{boundary_id}")
async def get_boundary(boundary_id: str, tenant: str = Depends(get_tenant)):
    b = authorization.for_tenant(tenant).get(boundary_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return b.model_dump()


@router.get("/boundaries/agent/{agent}")
async def get_agent_boundary(agent: str, tenant: str = Depends(get_tenant)):
    """取某Agent当前生效边界（当前租户内）"""
    b = authorization.for_tenant(tenant).get_for_agent(agent)
    if not b:
        return {"tenant_id": tenant, "boundary": None, "agent": agent}
    return {"tenant_id": tenant, "boundary": b.model_dump(), "agent": agent}


@router.post("/boundaries")
async def create_boundary(req: AuthBoundaryCreate, tenant: str = Depends(get_tenant)):
    """创建授权边界（当前租户内）"""
    b = authorization.for_tenant(tenant).create(req)
    return {"tenant_id": tenant, "id": b.id, "name": b.name, "status": "created", "boundary": b.model_dump()}


@router.put("/boundaries/{boundary_id}")
async def update_boundary(boundary_id: str, req: AuthBoundaryCreate, tenant: str = Depends(get_tenant)):
    """全量更新授权边界（当前租户内）"""
    b = authorization.for_tenant(tenant).update(boundary_id, req)
    if not b:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return {"tenant_id": tenant, "id": boundary_id, "status": "updated", "boundary": b.model_dump()}


@router.patch("/boundaries/{boundary_id}")
async def patch_boundary(boundary_id: str, req: UpdateBoundaryRequest, tenant: str = Depends(get_tenant)):
    """局部更新授权边界（当前租户内）"""
    scope = authorization.for_tenant(tenant)
    cur = scope.get(boundary_id)
    if not cur:
        raise HTTPException(status_code=404, detail="Boundary not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    from src.runtime.models.authorization import AuthBoundaryCreate
    merged = cur.model_dump()
    merged.update(updates)
    merged.pop("id", None)
    merged.pop("created_at", None)
    merged.pop("updated_at", None)
    updated = scope.update(boundary_id, AuthBoundaryCreate(**merged))
    return {"tenant_id": tenant, "id": boundary_id, "status": "patched", "boundary": updated.model_dump()}


@router.delete("/boundaries/{boundary_id}")
async def delete_boundary(boundary_id: str, tenant: str = Depends(get_tenant)):
    ok = authorization.for_tenant(tenant).delete(boundary_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return {"tenant_id": tenant, "id": boundary_id, "status": "deleted"}
