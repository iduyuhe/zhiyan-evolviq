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

S2 v30.5 β 新增（租户订阅规则——「抓取共享、语义隔离」消费层）：
    GET    /environment/subscriptions           当前租户订阅视图（显式规则+默认模板）
    PUT    /environment/subscriptions/{name}    新建/更新规则（先测试后保存闸门；超免费额度 402）
    DELETE /environment/subscriptions/{name}    删除规则（回落行业默认模板）
    GET    /environment/feed                    租户过滤后的环境信号流（语义隔离）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.runtime.authn.deps import require_auth
from src.runtime.context import get_current_tenant
from src.runtime.env_sources.manager import env_manager
from src.runtime.env_perception import env_review
from src.runtime import env_subscription_store as _sub_mod
from src.runtime.env_subscription_store import QuotaExceeded, env_subscription_store
from src.runtime.uns import uns, CHANNEL_ENVIRONMENT
from src.runtime.unlock_map import progress_view
from src.runtime.usage_meter import usage_meter
from src.runtime.platform_insight_store import platform_insight_store

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
    result = await env_manager.pull(name, limit=limit)
    # G5 轨道二：拉取真实情报后派生平台建议（去重幂等，透明标注 platform）
    try:
        await platform_insight_store.generate_from_environment(tenant_id="default")
    except Exception as e:
        logger.warning(f"⚠️ 平台建议派生失败（不破管）：{e}")
    return result


@router.post("/pull")
async def pull_all(limit: int = 10):
    result = await env_manager.pull_all(limit=limit)
    # G5 轨道二：拉取真实情报后派生平台建议（去重幂等，透明标注 platform）
    try:
        await platform_insight_store.generate_from_environment(tenant_id="default")
    except Exception as e:
        logger.warning(f"⚠️ 平台建议派生失败（不破管）：{e}")
    return result


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


# ============ S2 v30.5 β：租户订阅规则（语义隔离消费层） ============


class SubscriptionRequest(BaseModel):
    """订阅规则请求体（β1 筛选规则模型）"""

    enabled: bool = True
    credibility_min: str = Field(default="general", description="official|authoritative|general")
    keywords_include: list[str] = Field(default_factory=list)
    keywords_exclude: list[str] = Field(default_factory=list)
    poll_interval_sec: int = Field(default=3600, ge=60)
    force: bool = Field(default=False, description="连通性测试失败时是否强制保存")


def _known_source_names() -> list[str]:
    return [s["name"] for s in env_manager.list()]


@router.get("/subscriptions")
async def list_subscriptions():
    tenant = get_current_tenant()
    names = _known_source_names()
    return {
        "tenant_id": tenant,
        "subscriptions": env_subscription_store.list_for(tenant, names),
        "enabled_count": env_subscription_store.enabled_count(tenant, names),
        "free_max_sources": _sub_mod.FREE_MAX_SOURCES,
    }


@router.put("/subscriptions/{source_name}")
async def upsert_subscription(source_name: str, req: SubscriptionRequest):
    tenant = get_current_tenant()
    names = _known_source_names()
    if source_name not in names:
        raise HTTPException(status_code=404, detail=f"未知环境源：{source_name}（可选：{names}）")
    # 先测试后保存闸门（§4.4）：启用时先探源；失败须 force 才落盘
    test_result = None
    if req.enabled:
        test_result = await env_manager.test(source_name)
        if not test_result.get("ok") and not req.force:
            raise HTTPException(
                status_code=409,
                detail={"message": "源连通性测试未通过，未保存（可 force=true 强制保存）",
                        "test": test_result},
            )
    try:
        sub = await env_subscription_store.upsert(
            tenant,
            source_name,
            enabled=req.enabled,
            credibility_min=req.credibility_min,
            keywords_include=req.keywords_include,
            keywords_exclude=req.keywords_exclude,
            poll_interval_sec=req.poll_interval_sec,
            known_sources=names,
        )
    except QuotaExceeded as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "saved", "subscription": sub, "test": test_result}


@router.delete("/subscriptions/{source_name}")
async def delete_subscription(source_name: str):
    tenant = get_current_tenant()
    ok = await env_subscription_store.delete(tenant, source_name)
    if not ok:
        raise HTTPException(status_code=404, detail="该源无显式规则（当前即行业默认模板）")
    return {"status": "deleted", "source_name": source_name, "fallback": "default_template"}


@router.get("/feed")
async def tenant_feed(n: int = 50):
    """租户可见环境信号流：平台信号池 × 本租户订阅规则（语义隔离）× 日额度计量。

    免费额度（#309）：当日去重后新信号 ≤ ZHIYAN_FREE_DAILY_SIGNALS（默认 50）。
    超限不 402（避免面板轮询雪崩）——截断下发并在 quota.exhausted 提示升级。

    G5 轨道二（#314）：合并「平台建议」（kind=platform_insight）与真实情报（kind=intelligence）
    相邻呈现。平台建议由智衍平台基于真实情报派生、透明标注、不计入外部信号日额度。
    """
    tenant = get_current_tenant()
    pool = uns.query(channel=CHANNEL_ENVIRONMENT, n=max(n * 3, 100))
    filtered = env_subscription_store.filter_signals(tenant, pool, _known_source_names())
    allowed, quota = await usage_meter.consume_signals(tenant, filtered[-n:])

    # 真实情报打 kind=intelligence
    intel = [{**s, "kind": "intelligence"} for s in allowed]

    # 平台建议（共享池）→ 归一为与信号同形结构，kind=platform_insight
    insights = platform_insight_store.list_for(tenant_id="default", n=n)
    insight_items = [
        {
            "id": ins["id"],
            "source": "platform://zhiyan/suggestion",
            "credibility": "platform",
            "payload": {
                "title": ins["title"],
                "content": ins["content"],
                "based_on": ins.get("based_on", []),
            },
            "entities": [b.get("title", "") for b in ins.get("based_on", []) if isinstance(b, dict)],
            "ts": ins["ts"],
            "kind": "platform_insight",
        }
        for ins in insights
    ]

    # 相邻呈现：真实情报 + 平台建议按 ts 倒序合并（平台建议不挤占外部信号日额度）
    merged = sorted(intel + insight_items, key=lambda x: x.get("ts") or 0, reverse=True)[:n]
    return {
        "tenant_id": tenant,
        "signals": merged,
        "pool_size": len(pool),
        "visible": len(filtered),
        "platform_insight_count": len(insight_items),
        "quota": quota,
    }


@router.get("/platform-insights")
async def list_platform_insights(n: int = 50):
    """G5 轨道二：平台建议列表（智衍平台基于真实情报透明派生，credibility=platform）。

    共享池：对所有租户可见，不含任何租户私有信息。每条带 based_on 透明溯源其依据的真实情报。
    """
    items = platform_insight_store.list_for(tenant_id="default", n=n)
    return {"tenant_id": "default", "count": len(items), "insights": items}


@router.get("/quota")
async def tenant_quota():
    """当前租户免费额度视图（源数 + 日信号 + 月解读；#310 解锁进度视图消费）。"""
    tenant = get_current_tenant()
    view = usage_meter.view(tenant)
    names = _known_source_names()
    view["metrics"]["env_sources"] = {
        "used": env_subscription_store.enabled_count(tenant, names),
        "limit": None if view["unlimited"] else _sub_mod.FREE_MAX_SOURCES,
        "period": "static",
    }
    return view


@router.get("/unlock-progress")
async def unlock_progress():
    """无感转型三圈解锁进度（#310）。

    事实进度 + 下一步说明；F4 纪律：不推销、不弹窗——前端相邻呈现。
    附带 quota 摘要，前端一次请求可渲染完整「解锁进度」视图。
    """
    tenant = get_current_tenant()
    view = progress_view(tenant)
    view["quota"] = usage_meter.view(tenant)
    return view
