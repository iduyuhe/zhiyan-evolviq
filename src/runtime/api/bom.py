"""BOM 上传与毛利影响测算 API（S2-5，#311）

信任爬梯③价值跳变样板：
    POST /bom/preview        「先测试后保存」闸门——只解析不落盘，返回明细预览
    POST /bom/upload         解析 + 落盘（成功即达信任爬梯③：中圈解锁+免限额）
    GET  /bom                本租户 BOM 清单
    GET  /bom/{id}           单份 BOM（含明细）
    DELETE /bom/{id}         删除
    GET  /bom/{id}/margin-impact  行情信号 × BOM → 物料成本/毛利影响测算

纪律：
- 上传即价值：upload 响应内嵌一次 margin_impact（用户第一秒看到跳变）。
- 事实锚点：测算只用信号中出现的百分比，抽不出数字只进关注清单。
- 路由裸前缀 /bom（nginx /api 剥离铁律）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.runtime.authn.deps import require_auth
from src.runtime.bom_store import BomParseError, bom_store, parse_bom
from src.runtime.context import get_current_tenant
from src.runtime.uns import uns, CHANNEL_ENVIRONMENT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bom", tags=["bom"], dependencies=[Depends(require_auth)])


class BomUploadRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content: str = Field(..., description="CSV 文本或 JSON 数组", max_length=512_000)
    product_name: str = Field("", max_length=255)


def _market_signals(n: int = 200) -> list[dict]:
    return uns.query(channel=CHANNEL_ENVIRONMENT, n=n)


@router.post("/preview")
async def preview_bom(req: BomUploadRequest):
    """先测试后保存闸门：只解析不落盘。解析失败 422 + 可读原因。"""
    try:
        items = parse_bom(req.content, req.filename)
    except BomParseError as e:
        raise HTTPException(status_code=422, detail=f"BOM 解析失败：{e}")
    total = round(sum(i["cost"] for i in items), 2)
    return {
        "status": "ok",
        "filename": req.filename,
        "item_count": len(items),
        "total_material_cost": total,
        "items": items[:20],
        "truncated": len(items) > 20,
    }


@router.post("/upload")
async def upload_bom(req: BomUploadRequest):
    """解析 + 落盘。成功即达信任爬梯③（中圈解锁 + 免限额），响应内嵌首次测算。"""
    tenant = get_current_tenant()
    try:
        items = parse_bom(req.content, req.filename)
    except BomParseError as e:
        raise HTTPException(status_code=422, detail=f"BOM 解析失败：{e}")
    record = await bom_store.save(tenant, req.filename, req.product_name, items)
    logger.info(f"📄 BOM 上传：tenant={tenant} file={req.filename} items={len(items)}")
    # 上传即价值：立即用现有行情信号做一次测算
    try:
        impact = bom_store.margin_impact(tenant, record["id"], _market_signals())
    except Exception as e:  # 测算失败不影响上传成功
        logger.warning(f"⚠️ 上传后首测算失败：{e}")
        impact = None
    from src.runtime.unlock_map import current_circle

    return {
        "status": "uploaded",
        "bom": record,
        "margin_impact": impact,
        "current_circle": current_circle(tenant),  # 上传后即时圈层（价值跳变可见）
    }


@router.get("")
async def list_boms():
    tenant = get_current_tenant()
    return {"tenant_id": tenant, "boms": bom_store.list_for(tenant)}


@router.get("/{bom_id}")
async def get_bom(bom_id: str):
    rec = bom_store.get(get_current_tenant(), bom_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    return rec


@router.delete("/{bom_id}")
async def delete_bom(bom_id: str):
    ok = await bom_store.delete(get_current_tenant(), bom_id)
    if not ok:
        raise HTTPException(status_code=404, detail="BOM 不存在")
    return {"status": "deleted", "bom_id": bom_id}


@router.get("/{bom_id}/margin-impact")
async def margin_impact(bom_id: str):
    """行情 × BOM 毛利影响测算（可随行情更新反复调用）。"""
    tenant = get_current_tenant()
    try:
        return bom_store.margin_impact(tenant, bom_id, _market_signals())
    except KeyError:
        raise HTTPException(status_code=404, detail="BOM 不存在")
