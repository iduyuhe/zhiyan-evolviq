"""环境感知第⑥路 API（v30.0 α）

端点（全部受 JWT 门禁；nginx 剥 /api 前缀 → 此处一律裸前缀 /environment）：
    GET  /environment                      总览（源清单 + 信号量 + 审核队列计数）
    GET  /environment/sources              三类源状态
    GET  /environment/sources/{name}/test  单源连通性测试
    POST /environment/sources/{name}/pull  手动拉取单源（limit 可选）
    POST /environment/pull                 拉取全部源
    GET  /environment/signals              最近环境信号（n 可选）
    GET  /environment/review               _needs_review 审核队列（非官方信号）
    POST /environment/review/{id}/approve  人工批准 → 锚定
    POST /environment/review/{id}/reject   人工驳回 → 丢弃
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.runtime.authn.deps import require_auth
from src.runtime.env_sources.manager import env_manager
from src.runtime.env_perception import env_review
from src.runtime.uns import uns, CHANNEL_ENVIRONMENT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/environment", tags=["environment"], dependencies=[Depends(require_auth)])


@router.get("")
async def environment_overview():
    counts = uns.channel_counts()
    return {
        "sources": env_manager.list(),
        "signal_count": counts.get(CHANNEL_ENVIRONMENT, 0),
        "review": env_review.counts(),
    }


@router.get("/sources")
async def list_sources():
    return {"sources": env_manager.list()}


@router.get("/sources/{name}/test")
async def test_source(name: str):
    return await env_manager.test(name)


@router.post("/sources/{name}/pull")
async def pull_source(name: str, limit: int = 10):
    return await env_manager.pull(name, limit=limit)


@router.post("/pull")
async def pull_all(limit: int = 10):
    return await env_manager.pull_all(limit=limit)


@router.get("/signals")
async def list_signals(n: int = 50):
    return {"signals": uns.query(channel=CHANNEL_ENVIRONMENT, n=n)}


@router.get("/review")
async def list_review(status: str = "pending"):
    return {"items": env_review.list(status=None if status == "all" else status),
            "counts": env_review.counts()}


@router.post("/review/{item_id}/approve")
async def approve_review(item_id: str):
    item = env_review.approve(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="条目不存在或已处理")
    return {"status": "approved", "item": item}


@router.post("/review/{item_id}/reject")
async def reject_review(item_id: str):
    item = env_review.reject(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="条目不存在或已处理")
    return {"status": "rejected", "item": item}
