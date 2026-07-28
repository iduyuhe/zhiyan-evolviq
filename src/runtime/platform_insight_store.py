"""平台建议存储（S2 v30.5 β · G5 轨道二 platform_insight）

职责：
- 基于真实环境情报（UNS environment 路）规则化派生「智衍平台建议」，
  每条建议透明引用其依据的真实情报（based_on），credibility="platform"。
- 去重：同一真实信号 + 同一模板只生成一次（sig_ref 幂等）。
- 持久化：db 可用落库，重启恢复；db 不可用降级内存态（与 feedback_store/bom_store 同构）。
- 发布：生成即 publish 到 UNS platform_insight 路，供 /environment/feed 合并呈现。

红线（F4 可信治理）：平台建议 credibility 永远不是 official/authoritative/general，
  在 feed 中 kind="platform_insight"，前端透明标注「来自智衍平台的建议」，绝不伪装成情报。
平台建议为平台级共享池（tenant_id="default"），不含任何租户私有信息，对所有租户可见。
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from sqlalchemy import select

from src.common import db
from src.runtime.uns import (
    CRED_PLATFORM,
    CHANNEL_ENVIRONMENT,
    CHANNEL_PLATFORM_INSIGHT,
    uns,
)

logger = logging.getLogger(__name__)


# ---------- 规则化派生：基于真实情报关键词 → 平台建议（诚实引用，不臆造） ----------
def _derive(sig: dict) -> dict | None:
    """从一条真实环境情报派生平台建议；无匹配返回 None。

    返回的 dict：{template_key, title, content, based_on}
    based_on 透明溯源其依据的真实情报（signal_id / source / title）。
    """
    payload = sig.get("payload") or {}
    title = str(payload.get("title") or payload.get("summary") or payload.get("name") or "")
    content = str(payload.get("content") or payload.get("highlight") or "")
    text = title + " " + content
    src = str(sig.get("source") or "")
    sig_id = sig.get("id")
    based_on = [{"signal_id": sig_id, "source": src, "title": title[:160]}]

    # 行业对标 + 排产/APS/OEE/决策实时化 → 建议评估 APS 智能排产
    if "benchmark" in src and any(k in text for k in ("排产", "APS", "OEE", "决策实时化", "分钟级响应")):
        return {
            "template_key": "benchmark_aps",
            "title": "建议评估 APS 智能排产模块",
            "content": (
                f"基于您关注的行业对标【{title[:40]}】，智衍平台建议优先评估 APS 智能排产模块，"
                f"以缩小与标杆企业在「决策实时化率 / OEE」上的差距。可在「会话」中发起一次排产诊断。"
            ),
            "based_on": based_on,
        }

    # 政策/对标提及补贴/改造 → 建议梳理可申报补贴
    if ("policy" in src or "benchmark" in src) and any(k in text for k in ("补贴", "改造")):
        return {
            "template_key": "subsidy",
            "title": "建议梳理可申报的智能化改造补贴",
            "content": (
                f"基于【{title[:40]}】，智衍平台建议梳理可申报的智能化改造 / 数字化转型补贴，"
                f"降低转型前期投入。可上传政策原文由智能体提取申报要点。"
            ),
            "based_on": based_on,
        }

    # 原材料行情上行/波动 → 建议复核 BOM 毛利敞口
    if "market" in src and any(
        k in text for k in ("上行", "上涨", "提升", "攀升", "上升", "走高", "波动", "紧缺", "收紧", "走强")
    ):
        mat = _first_material(payload, text)
        return {
            "template_key": "market_bom",
            "title": f"原材料「{mat}」波动，建议复核 BOM 毛利敞口",
            "content": (
                f"原材料「{mat}」价格呈上行/波动迹象（依据行情【{title[:30]}】）。"
                f"智衍平台建议用「BOM 毛利测算」工具复核成本传导影响，提前锁定敞口。"
            ),
            "based_on": based_on,
        }

    # 行业对标兜底 → 建议纳入对标看板
    if "benchmark" in src:
        return {
            "template_key": "benchmark_board",
            "title": "建议纳入对标看板",
            "content": (
                f"基于行业对标【{title[:40]}】，智衍平台建议将其关键指标（决策实时化率 / OEE / 能碳）"
                f"纳入贵司对标看板，持续追踪与标杆的差距。"
            ),
            "based_on": based_on,
        }

    # 政策兜底 → 建议纳入政策跟踪清单
    if "policy" in src:
        return {
            "template_key": "policy_watch",
            "title": "建议纳入政策跟踪清单",
            "content": (
                f"基于政策【{title[:40]}】，智衍平台建议将其纳入常态化政策跟踪清单，"
                f"由智能体定期提取对业务的影响与可行动项。"
            ),
            "based_on": based_on,
        }

    return None


def _first_material(payload: dict, text: str) -> str:
    for e in payload.get("entities") or []:
        if isinstance(e, str) and ("MAT:" in e or "物料" in e):
            return e.split(":", 1)[-1][:20]
    for kw in ("电解铜", "铜", "锂", "铝", "钢", "镍", "树脂", "芯片", "MLCC"):
        if kw in text:
            return kw
    return "关键原料"


class PlatformInsightStore:
    """平台建议注册表（进程级单例语义）"""

    def __init__(self) -> None:
        self._by_id: dict[str, "PlatformInsight"] = {}
        self._signatures: set[str] = set()  # 去重：sig_ref 集合

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """从库加载全部平台建议到内存（main lifespan 在 init_db 之后调用；幂等）。"""
        if not db.db_available or db.async_session is None:
            logger.warning("⚠️ 平台建议存储降级为内存态（db 不可用），重启即失")
            return
        try:
            from src.runtime.models.platform_insight import PlatformInsight

            async with db.async_session() as s:
                rows = (await s.execute(select(PlatformInsight))).scalars().all()
                for r in rows:
                    self._by_id[r.id] = r
                    self._signatures.add(r.sig_ref)
            logger.info(f"✅ 平台建议加载：{len(self._by_id)} 条")
        except Exception as e:
            logger.warning(f"⚠️ 平台建议加载失败，降级内存态：{e}")

    # ---------- 规则化派生（G5 轨道二） ----------
    async def generate_from_environment(self, limit: int = 200, tenant_id: str = "default") -> int:
        """基于 UNS environment 路的真实情报，规则化派生平台建议。

        去重：同 (tenant_id, source, template_key, 信号标题) 只生成一次——以内容为准，
        同一真实情报被重复拉取（不同 signal_id、相同标题）不会重复生成平台建议。
        派生即发布到 UNS platform_insight 路，供 /feed 合并呈现。
        """
        sigs = uns.query(channel=CHANNEL_ENVIRONMENT, n=limit)
        generated = 0
        for sig in sigs:
            sugg = _derive(sig)
            if not sugg:
                continue
            payload = sig.get("payload") or {}
            title = str(payload.get("title") or payload.get("summary") or payload.get("name") or "")
            src = str(sig.get("source") or "")
            title_key = (title or sugg["title"])[:50]
            signature = f"{tenant_id}|{src}|{sugg['template_key']}|{title_key}"
            if signature in self._signatures:
                continue
            self._signatures.add(signature)
            now = time.time()
            obj = self._make_obj(
                tenant_id=tenant_id,
                title=sugg["title"][:300],
                content=sugg["content"],
                sig_ref=signature[:200],
                based_on=sugg["based_on"],
                ts=now,
            )
            self._by_id[obj.id] = obj
            await self._persist(obj)
            # 发布到 UNS platform_insight 路（透明标注 platform 建议）
            uns.publish_platform_insight(
                source="platform://zhiyan/suggestion",
                payload={
                    "title": obj.title,
                    "content": obj.content,
                    "based_on": sugg["based_on"],
                },
                entities=[b.get("title", "") for b in sugg["based_on"] if isinstance(b, dict)],
                tenant_id=tenant_id,
            )
            generated += 1
        if generated:
            logger.info(f"💡 平台建议新生成 {generated} 条（共享池，tenant={tenant_id}）")
        return generated

    def _make_obj(self, *, tenant_id, title, content, sig_ref, based_on, ts) -> "PlatformInsight":
        from src.runtime.models.platform_insight import PlatformInsight

        return PlatformInsight(
            id=uuid.uuid4().hex[:16],
            tenant_id=tenant_id,
            title=title,
            content=content,
            sig_ref=sig_ref,
            based_on=json.dumps(based_on, ensure_ascii=False),
            credibility=CRED_PLATFORM,
            confidence=1.0,
            ts=ts,
        )

    async def _persist(self, obj: "PlatformInsight") -> None:
        if not (db.db_available and db.async_session is not None):
            return
        try:
            from src.runtime.models.platform_insight import PlatformInsight

            async with db.async_session() as s:
                existing = await s.get(PlatformInsight, obj.id)
                if existing is None:
                    s.add(obj)
                else:
                    existing.title = obj.title
                    existing.content = obj.content
                    existing.sig_ref = obj.sig_ref
                    existing.based_on = obj.based_on
                await s.commit()
        except Exception as e:
            logger.warning(f"⚠️ 平台建议持久化失败（内存已更新）：{e}")

    # ---------- 查询 ----------
    def list_for(self, tenant_id: str | None = None, n: int = 50) -> list[dict]:
        """平台建议列表（共享池，tenant_id 参数保留以便未来分租户扩展；当前忽略过滤）。

        按 ts 倒序返回，最多 n 条，每条带 kind="platform_insight"。
        """
        items = list(self._by_id.values())
        items.sort(key=lambda o: o.ts, reverse=True)
        return [o.to_dict() for o in items[:n]]

    def count(self) -> int:
        return len(self._by_id)

    def clear(self) -> None:
        """测试清理：清空内存与去重集（不删库，测试用内存态即可）。"""
        self._by_id.clear()
        self._signatures.clear()


# 进程级单例
platform_insight_store = PlatformInsightStore()
