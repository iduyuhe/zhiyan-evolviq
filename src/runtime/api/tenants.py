"""租户管理 API——多租户自注册与管理

- POST /tenants/register：自助注册新租户，一次性返回明文 api_key
- GET  /tenants/me：查询当前租户信息（需 X-Tenant-Key）
- POST /tenants/rotate：轮换当前租户密钥（需 X-Tenant-Key，返回新明文 key）
- DELETE /tenants/me：注销当前租户（默认租户不可删）
- GET  /tenants：列出全部租户（需 X-Platform-Admin-Key）
- PUT  /tenants/gateway-config：设置当前租户的工业网关连接参数覆写（需 X-Tenant-Key）
- GET  /tenants/gateway-config：读取当前租户网关配置（需 X-Tenant-Key）

设计：默认租户 `default` 始终存在，匿名请求归属它。注册为开放能力（SaaS 自助开通）；
平台级管理（列全部/强制操作）需配置 TENANT_ADMIN_KEY 环境变量。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.runtime.api.deps import get_tenant, get_platform_admin
from src.runtime.tenant_store import tenant_store
from src.runtime.models.tenant import DEFAULT_TENANT_ID

router = APIRouter(prefix="/tenants", tags=["tenants"])


class RegisterRequest(BaseModel):
    name: str


class GatewayConfigRequest(BaseModel):
    # 工业协议网关连接参数覆写（全部可选；只传需要覆写的字段）
    modbus_host: str | None = None
    modbus_port: int | None = None
    mqtt_broker: str | None = None
    mqtt_port: int | None = None
    opcua_endpoint: str | None = None
    ipc_cfx_broker: str | None = None


@router.post("/register")
async def register_tenant(req: RegisterRequest):
    """自助注册新租户。返回明文 api_key（仅此一次可见，请妥善保存）。"""
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="租户名称不能为空")
    tid, api_key = await tenant_store.register(name)
    return {
        "tenant_id": tid,
        "name": name,
        "api_key": api_key,
        "note": "请妥善保存此 api_key；后续调用在请求头携带 X-Tenant-Key: <api_key> 即可归属该租户。",
    }


@router.get("/me")
async def get_me(tenant: str = Depends(get_tenant)):
    """查询当前租户信息。"""
    t = tenant_store.get(tenant)
    if not t:
        raise HTTPException(status_code=404, detail="租户不存在")
    return t.to_dict()


@router.post("/rotate")
async def rotate_key(tenant: str = Depends(get_tenant)):
    """轮换当前租户密钥。返回新的明文 api_key（旧 key 立即失效）。"""
    new_key = await tenant_store.rotate(tenant)
    if not new_key:
        raise HTTPException(status_code=400, detail="密钥轮换失败")
    return {"tenant_id": tenant, "api_key": new_key, "note": "旧密钥已失效，请更新调用方配置。"}


@router.delete("/me")
async def delete_me(tenant: str = Depends(get_tenant)):
    """注销当前租户（默认租户不可删）。"""
    if tenant == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="默认租户不可删除")
    ok = await tenant_store.delete(tenant)
    if not ok:
        raise HTTPException(status_code=400, detail="租户删除失败")
    return {"tenant_id": tenant, "status": "deleted"}


@router.get("")
async def list_tenants(_admin: str = Depends(get_platform_admin)):
    """列出全部租户（平台管理员）。"""
    return {
        "total": len(tenant_store.list()),
        "tenants": [t.to_dict() for t in tenant_store.list()],
    }


@router.put("/gateway-config")
async def set_gateway_config(req: GatewayConfigRequest, tenant: str = Depends(get_tenant)):
    """设置当前租户的工业网关连接参数覆写（缺省字段沿用平台共享网关）。"""
    cfg = {k: v for k, v in req.model_dump().items() if v is not None}
    ok = await tenant_store.set_gateway_config(tenant, cfg or None)
    if not ok:
        raise HTTPException(status_code=400, detail="网关配置设置失败")
    return {"tenant_id": tenant, "gateway_config": cfg or None, "note": "配置生效；该租户后续网关调用将使用隔离连接。"}


@router.get("/gateway-config")
async def get_gateway_config(tenant: str = Depends(get_tenant)):
    """读取当前租户网关配置（None 表示使用平台共享网关）。"""
    return {"tenant_id": tenant, "gateway_config": tenant_store.get_gateway_config(tenant)}
