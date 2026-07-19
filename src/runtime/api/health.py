"""健康检查API"""

from fastapi import APIRouter

from src.common.db import db_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "智衍 EvolvIQ Runtime",
        "version": "0.1.0",
        "db": db_status(),
    }
