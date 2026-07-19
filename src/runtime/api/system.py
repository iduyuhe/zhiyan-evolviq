"""系统状态 API——数据层健康与模式"""

from fastapi import APIRouter

from src.common.db import db_status

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/db")
async def db_health():
    """数据库状态：是否可用、当前模式（postgresql/sqlite/none）、脱敏连接串。"""
    return db_status()
