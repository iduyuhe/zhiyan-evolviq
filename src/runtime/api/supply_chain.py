"""供应链数据API——BOM、PO、库存等工业数据接口"""

from fastapi import APIRouter

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])


@router.get("/bom")
async def list_boms():
    return {"boms": [], "total": 0}


@router.get("/bom/{bom_id}")
async def get_bom(bom_id: str):
    return {"bom_id": bom_id, "items": []}


@router.get("/check/{bom_id}")
async def check_supply(bom_id: str):
    """触发齐套检查"""
    return {"bom_id": bom_id, "status": "ok", "completeness_pct": 0}


@router.get("/inventory")
async def get_inventory():
    return {"items": [], "total": 0}


@router.get("/po")
async def list_pos(status: str | None = None):
    return {"pos": [], "total": 0}
