"""企业现状描述接口 API（两阶段实例化框架 · Phase 2 产品化）

契约：docs/ENTERPRISE_PROFILE_SCHEMA.md（D1 混合形态 + D2 凭证铁律 + D3 案例库驱动推荐）。

- POST /enterprise/profile           录入/更新企业现状画像（租户取自 JWT）
- GET  /enterprise/profile           查看本租户画像（不含任何凭证内容）
- POST /enterprise/credentials       凭证入 vault（加密存储，仅回 vault_id 引用）
- GET  /enterprise/credentials       本租户凭证引用列表（仅元数据）
- DELETE /enterprise/credentials/{vault_id}  删除本租户凭证
- GET  /enterprise/recommendations   案例库驱动的接口推荐三态清单（enterprise_onboarding agent）

🔴 红线：任何响应绝不含凭证明文/密文；跨租户不可见；narrative/legal_entities 属私域仅本租户可读。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.runtime.authn.deps import require_auth
from src.runtime.enterprise_store import (
    CREDENTIAL_KINDS,
    INTENT_CHOICES,
    PROFILE_INDUSTRIES,
    credential_vault,
    profile_store,
)

router = APIRouter(prefix="/enterprise", tags=["enterprise"])


class SystemsIn(BaseModel):
    erp: str | None = None            # 用友/金蝶/SAP/Oracle/自研/无
    mes: str | None = None            # 自有/第三方/无
    gateway: list[str] = []           # OPC-UA/Modbus/AMQP/MQTT
    social: list[str] = []            # 企业微信/钉钉/邮件
    knowledge_base: bool = False


class IntentIn(BaseModel):
    free_tier_ok: bool = True
    internal_connect: str = "暂不"     # 暂不/评估后/现在就开
    concerns: str = Field(default="", max_length=500)


class ProfileIn(BaseModel):
    industry: str                      # 必填，匹配案例库行业
    region: str = Field(default="", max_length=60)
    legal_entities: list[str] = []
    org_scale: str = ""                # <50 / 50-200 / 200-1000 / 1000+
    revenue_band: str = ""             # 仅内部校准用
    systems: SystemsIn = SystemsIn()
    intent: IntentIn = IntentIn()
    narrative: str = Field(default="", max_length=2000)


class CredentialIn(BaseModel):
    kind: str                          # erp_writeback/gateway_opcua/social_wecom/social_dingtalk/email_imap
    secret: dict                       # 明文仅在本请求内存中，入 vault 即密文


@router.post("/profile")
async def upsert_profile(req: ProfileIn, u: dict = Depends(require_auth)):
    """录入/更新企业现状画像。租户取自 JWT，客户端不可指定。"""
    if req.industry not in PROFILE_INDUSTRIES:
        raise HTTPException(status_code=400, detail=f"industry 须为 {PROFILE_INDUSTRIES} 之一")
    if req.intent.internal_connect not in INTENT_CHOICES:
        raise HTTPException(status_code=400, detail=f"internal_connect 须为 {INTENT_CHOICES} 之一")
    saved = profile_store.upsert(u["tenant_id"], req.model_dump())
    return {"status": "saved", "profile": saved}


@router.get("/profile")
async def get_profile(u: dict = Depends(require_auth)):
    """查看本租户画像（私域数据，跨租户不可见；不含任何凭证内容）。"""
    p = profile_store.get(u["tenant_id"])
    return {"exists": p is not None, "profile": p}


@router.post("/credentials")
async def store_credential(req: CredentialIn, u: dict = Depends(require_auth)):
    """凭证入 vault：加密存储，仅返回 vault_id 引用。🔴 绝不回显明文。"""
    if req.kind not in CREDENTIAL_KINDS:
        raise HTTPException(status_code=400, detail=f"kind 须为 {CREDENTIAL_KINDS} 之一")
    try:
        ref = credential_vault.store(u["tenant_id"], req.kind, req.secret)
    except RuntimeError as e:  # fail-closed：加密不可用拒存
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "stored", "ref": ref}


@router.get("/credentials")
async def list_credentials(u: dict = Depends(require_auth)):
    """本租户凭证引用列表（仅元数据：vault_id/kind/created_at）。"""
    refs = credential_vault.list_refs(u["tenant_id"])
    return {"total": len(refs), "refs": refs}


@router.delete("/credentials/{vault_id}")
async def delete_credential(vault_id: str, u: dict = Depends(require_auth)):
    """删除本租户凭证（跨租户操作静默 404）。"""
    ok = credential_vault.delete(vault_id, u["tenant_id"])
    if not ok:
        raise HTTPException(status_code=404, detail="凭证不存在")
    return {"status": "deleted", "vault_id": vault_id}


@router.get("/recommendations")
async def recommendations(u: dict = Depends(require_auth)):
    """案例库驱动的接口推荐三态清单（建议开通/待补凭证/暂不需要）。"""
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent

    result = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=u["tenant_id"])
    result["agent"] = "enterprise_onboarding"
    return result


# 幂等去重：同一 (tenant, equipment_id) 仅发布一次（与 UNS 同生命周期，容器内进程共享）
_seeded_equipment_keys: set[str] = set()


class SeedUnsIn(BaseModel):
    force: bool = False  # 强制重新发布（覆盖去重）


@router.post("/equipment/seed-uns")
async def seed_equipment_to_uns(req: SeedUnsIn, u: dict = Depends(require_auth)):
    """把本租户匹配的设备模板实例化进 UNS 事件流（gateway 通道），便于孪生大屏实时事件流展示。

    每台设备发布一条 gateway 事件（source=opcua://{id}、type=equipment_onboard、
    entities=[DEV:{id}]、tenant_id 快照、route_holon=machine 进入孪生体状态上行）。
    幂等：同一 (tenant, equipment_id) 默认仅发布一次，除非 force=True。
    """
    from src.runtime.uns import uns, CHANNEL_GATEWAY
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent

    tenant_id = u["tenant_id"]
    result = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tenant_id)
    equipments = (result.get("equipment_presets") or {}).get("equipments", [])
    if not equipments:
        return {"status": "no_equipment", "seeded": 0, "skipped": 0, "total": 0}

    seeded, skipped = 0, 0
    for eq in equipments:
        eid = eq.get("equipment_id")
        if not eid:
            continue
        key = f"{tenant_id}:{eid}"
        if key in _seeded_equipment_keys and not req.force:
            skipped += 1
            continue
        uns.publish(
            CHANNEL_GATEWAY,
            source=f"opcua://{eid}",
            type="equipment_onboard",
            payload={
                "equipment_id": eid,
                "name": eq.get("name"),
                "type_cn": eq.get("type_cn"),
                "vendor": eq.get("vendor"),
                "model": eq.get("model"),
                "mtbf_hours": eq.get("mtbf_hours"),
                "opcua_tag_count": eq.get("opcua_tag_count"),
                "tenant_id": tenant_id,
                "industry_cn": (result.get("equipment_presets") or {}).get("industry_cn"),
            },
            entities=[f"DEV:{eid}"],
            tenant_id=tenant_id,
            route_holon="machine",
        )
        _seeded_equipment_keys.add(key)
        seeded += 1
    return {
        "status": "ok",
        "seeded": seeded,
        "skipped": skipped,
        "total": len(equipments),
    }
