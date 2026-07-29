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
    GET    /environment/unlock-progress          无感转型三圈解锁进度（+ S3-5 推荐下一步）
    GET    /environment/agent-recommendations    S3-5 行为导航④：推荐下一值得解锁的智能体

S3 v31 γ 新增（共生进化环——§3.6）：
    POST   /environment/feedback              产品内零摩擦反馈（脱敏+匿名+建 from-customer Issue）
    GET    /environment/feedback/status        本租户反馈进度 + 48h SLA（仅本租户可见）
    GET    /environment/growth-profile         租户「成长档案」（使用天数/解锁圈层/贡献进化数）
    GET    /environment/evolution              「因你而进化」回告（仅与本租户反馈相关）
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.runtime.authn.deps import require_auth
from src.runtime.context import get_current_tenant
from src.runtime.env_sources.manager import env_manager
from src.runtime.env_perception import env_review
from src.runtime.signal_relevance import SOURCE_NAME_CATEGORY
from src.runtime.recommendation_feedback_store import (
    FB_ADOPT as REC_FB_ADOPT,
    FB_REJECT as REC_FB_REJECT,
    adjustments_for as rec_feedback_adjustments,
    record as fb_record,
)
from src.runtime import env_subscription_store as _sub_mod
from src.runtime.env_subscription_store import QuotaExceeded, env_subscription_store
from src.runtime.uns import uns, CHANNEL_ENVIRONMENT
from src.runtime.unlock_map import progress_view
from src.runtime.usage_meter import usage_meter
from src.runtime.platform_insight_store import platform_insight_store
from src.runtime.agent_recommendation import recommend_for_tenant
from src.runtime.symbiosis_store import (
    evolution_notifications,
    feedback_status,
    growth_profile,
    submit_feedback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/environment", tags=["environment"], dependencies=[Depends(require_auth)])


@router.get("")
async def environment_overview():
    counts = uns.channel_counts()
    # 研究案例模式（§3.7）：disclosure 以匿名"某某通讯公司"对外呈现，含入源清单
    sources = env_manager.list()
    return {
        "sources": sources,
        "signal_count": counts.get(CHANNEL_ENVIRONMENT, 0),
        "review": env_review.counts(),
    }


@router.get("/sources")
async def list_sources():
    # 研究案例模式（§3.7）：disclosure 以匿名"某某通讯公司"对外呈现，含入源清单
    sources = env_manager.list()
    return {"sources": sources}


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
    # 仅返回对租户开放订阅的源（tenant_facing=True）；平台级研究案例源（如 disclosure）不进租户视图/不占免费额度
    return [s["name"] for s in env_manager.list() if s.get("tenant_facing", True)]


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
async def tenant_feed(n: int = 50, include_suppressed: bool = False):
    """租户可见环境信号流：平台信号池 × 本租户订阅规则（语义隔离）× 日额度计量。

    免费额度（#309）：当日去重后新信号 ≤ ZHIYAN_FREE_DAILY_SIGNALS（默认 50）。
    超限不 402（避免面板轮询雪崩）——截断下发并在 quota.exhausted 提示升级。

    S3-2 相关性打分降噪（#317）：消费本租户行为画像（S3-1）+ 订阅规则，给每条真实情报
    打 relevance（score / target_agents / reason / suppressed），按相关性降序、低相关降噪
    （suppressed 默认不返回，?include_suppressed=true 可调试）；F4 透明标注打分依据。

    G5 轨道二（#314）：真实情报（已按相关性排序、高相关优先）在前，平台建议
    （kind=platform_insight）相邻在后。平台建议由智衍平台基于真实情报派生、透明标注、
    不计入外部信号日额度。
    """
    tenant = get_current_tenant()
    pool = uns.query(channel=CHANNEL_ENVIRONMENT, n=max(n * 3, 100))
    filtered = env_subscription_store.filter_signals(tenant, pool, _known_source_names())
    allowed, quota = await usage_meter.consume_signals(tenant, filtered[-n:])

    # S3-2：本租户画像 + 订阅 → 关注权重；真实情报逐条打分、降噪、按相关性降序
    from src.runtime.behavior_store import behavior_store
    from src.runtime.signal_relevance import derive_attention, rank_intelligence_signals

    profile = behavior_store.profile(tenant)
    subs = env_subscription_store.list_for(tenant, _known_source_names())
    attention = derive_attention(profile, subs)
    ranked_intel, suppressed_count = rank_intelligence_signals(
        allowed, attention, include_suppressed=include_suppressed
    )

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

    # 合并：真实情报（已按相关性降序，高相关优先）在前，平台建议相邻在后
    merged = (ranked_intel + insight_items)[:n]
    return {
        "tenant_id": tenant,
        "signals": merged,
        "pool_size": len(pool),
        "visible": len(filtered),
        "suppressed_count": suppressed_count,
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
    # S3-5 行为导航④（#319）：在当前圈层旁点亮「推荐下一步」（融入三圈视图，相邻呈现）
    view["recommended_next"] = recommend_for_tenant(tenant).get("recommended_next", [])
    return view


@router.get("/agent-recommendations")
async def agent_recommendations():
    """S3-5 行为导航④（#319）：推荐下一值得解锁的智能体（无感转型导航器）。

    按租户自身产品内行为（高频使用的智能体 / 关注的情报类目 / 已采纳源类目）派生
    「关注重点」，映射到三圈地图上的最短价值路径——推荐当前圈层之外（锁定态）的
    下一圈 agent，价值句式「你关注的 X，配合 Y，{agent} 能算出 Z」。

    F4 透明：每条推荐附 reasons（基于你最近的哪些行为），source=behavior 明示为
    租户自身行为派生（非共享平台建议）。🔴 严格租户内隔离，绝不跨租户。
    """
    tenant = get_current_tenant()
    return recommend_for_tenant(tenant)


@router.get("/source-recommendations")
async def source_recommendations():
    """S3-3 源推荐（#317，γ1）：按租户行业 / 物料（BOM）/ 行为画像推荐值得订阅的信息源。

    推荐呈 draft 形式（reasons 透明标注依据），由人审后在前端点「订阅」落盘——
    绝不静默自动订阅（F4 透明纪律 + 信任爬梯③付费闸门）。

    聚合：本租户已知源清单 + 本租户订阅规则 + 本租户 BOM 全量物料 + 本租户行为画像
    + 行业变量（ZHIYAN_INDUSTRY）。🔴 严格租户内隔离，绝不跨租户。
    """
    from src.runtime.behavior_store import behavior_store
    from src.runtime.bom_store import bom_store
    from src.runtime.source_recommendation import (
        apply_feedback,
        build_tenant_interest,
        recommend_sources,
    )

    tenant = get_current_tenant()
    names = _known_source_names()
    known = env_manager.list()
    subs = env_subscription_store.list_for(tenant, names)

    # 本租户行为画像（S3-1 供血）
    profile = behavior_store.profile(tenant)

    # 本租户 BOM 全量物料（list_for 已剔除 items，需逐份 get 取回物料名）
    materials: list[str] = []
    for rec in bom_store.list_for(tenant):
        full = bom_store.get(tenant, rec["id"])
        for it in (full or {}).get("items", []) or []:
            m = it.get("material")
            if m:
                materials.append(str(m))

    # 行业变量
    industry = (os.getenv("ZHIYAN_INDUSTRY", "") or "").strip()

    interest = build_tenant_interest(profile, materials, industry)
    recs = recommend_sources(known, subs, interest)

    # S3-4 采纳/驳回反哺（#318）：本租户反馈回流打分（F4 透明；🔴 仅本租户）
    adj = rec_feedback_adjustments(tenant)
    recs, feedback_applied = apply_feedback(recs, adj)

    return {
        "tenant_id": tenant,
        "industry": industry,
        "feedback_applied": feedback_applied,
        "feedback_count": adj.get("count", 0),
        "interest": {
            "category_interests": interest["category_interests"],
            "material_terms": sorted(interest["material_terms"])[:30],
            "material_by_category": interest["material_by_category"],
            "agent_by_category": interest["agent_by_category"],
            "industry_categories": sorted(interest["industry_categories"]),
        },
        "recommendations": recs,
    }


class RecommendationFeedbackRequest(BaseModel):
    """采纳/驳回推荐事件（#318 反哺入口）。

    与蓝弧后果回流同构：声明动作（adopt/reject）→ 立即回流推荐打分。
    target_kind 支持 source（信息源）/ category（类目）/ signal（情报 id）。
    """

    source_name: str | None = Field(default=None, description="推荐源名（target_kind=source 时必填）")
    action: str = Field(..., description="adopt=采纳 | reject=驳回")
    target_kind: str = Field(default="source", description="source | category | signal")


@router.post("/recommendations/feedback")
async def post_recommendation_feedback(req: RecommendationFeedbackRequest):
    """S3-4 采纳/驳回反哺（#318）：记录一次推荐采纳/驳回，回流推荐模型。

    返回 {status, category, adjustments_summary}。下次 GET /environment/source-recommendations
    即体现调整（F4 透明标注）。🔴 严格租户内隔离，反馈仅作用于本租户。
    """
    if req.action not in (REC_FB_ADOPT, REC_FB_REJECT):
        raise HTTPException(status_code=422, detail=f"action 须为 {REC_FB_ADOPT}/{REC_FB_REJECT}")

    tenant = get_current_tenant()

    if req.target_kind == "source":
        if not req.source_name:
            raise HTTPException(status_code=422, detail="target_kind=source 时 source_name 必填")
        names = _known_source_names()
        if req.source_name not in names:
            raise HTTPException(status_code=404, detail=f"未知环境源：{req.source_name}（可选：{names}）")
        category = SOURCE_NAME_CATEGORY.get(req.source_name)
        target_id = req.source_name
    elif req.target_kind == "category":
        if not req.source_name:
            raise HTTPException(status_code=422, detail="target_kind=category 时 source_name 填类目名（policy/market/benchmark）")
        category = req.source_name
        target_id = req.source_name
    else:  # signal
        if not req.source_name:
            raise HTTPException(status_code=422, detail="target_kind=signal 时 source_name 填信号 id")
        category = None
        target_id = req.source_name

    await fb_record(tenant, req.target_kind, target_id, req.action, category)
    adj = rec_feedback_adjustments(tenant)
    summary = {
        "category_boost": adj["category_boost"],
        "rejected_sources": adj["rejected_sources"],
        "rejected_categories": adj["rejected_categories"],
        "count": adj["count"],
    }
    return {
        "status": "recorded",
        "action": req.action,
        "target_kind": req.target_kind,
        "target_id": target_id,
        "category": category,
        "adjustments_summary": summary,
    }


# ===== S3-6 共生进化环（#320，MASTER §3.6） =====


class FeedbackRequest(BaseModel):
    kind: str = Field(..., description="praise(👍有用) / inaccurate(👎不准) / idea(💡我有想法) / other")
    text: str = Field(..., min_length=1, max_length=2000, description="反馈内容")
    anonymous: bool = True  # 默认匿名（§3.6 红线）


@router.post("/feedback")
async def post_feedback(req: FeedbackRequest, u: dict = Depends(require_auth)):
    """产品内零摩擦反馈入口（§3.6 步1）。

    自动脱敏（剥离邮箱/手机号/租户标识）+ 默认匿名 + 建 GitHub from-customer Issue（待审核）。
    Issue 创建失败不阻断——反馈已落内网，待运维发布。返回 tracking_id + 48h SLA 计时。
    🔴 未经脱敏/审核绝不出内网；租户取自 JWT。
    """
    view = await submit_feedback(
        tenant_id=u["tenant_id"],
        user=u.get("username"),
        kind=req.kind,
        text=req.text,
        anonymous=req.anonymous,
    )
    return view


@router.get("/feedback/status")
async def feedback_status_view():
    """本租户全部反馈进度 + 48h SLA（§3.6 步3 可溯源）。🔴 仅本租户。"""
    tenant = get_current_tenant()
    return {"tenant_id": tenant, "total": len(feedback_status(tenant)), "items": feedback_status(tenant)}


@router.get("/growth-profile")
async def growth_profile_view():
    """租户「成长档案」（§3.6 步4 被陪伴）。🔴 仅本租户可见。"""
    tenant = get_current_tenant()
    return growth_profile(tenant)


@router.get("/evolution")
async def evolution_view():
    """「因你而进化」回告（§3.6 步4）。仅返回与本租户反馈相关、已发布的内容。"""
    tenant = get_current_tenant()
    return {"tenant_id": tenant, "notifications": evolution_notifications(tenant)}
