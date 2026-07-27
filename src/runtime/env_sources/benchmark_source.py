"""环境源③：行业智能化对标（官方名录，credibility=official）—— G5 轨道一

live 模式：settings.env_benchmark_url 配置官方名录（试点示范/灯塔工厂等公开名单）后自动升级。
simulated 模式：确定性演示样本。
消费方：executive_cockpit（战略对标——真情报造差距感，G5 轨道一：这是真实行业情报，
不是平台广告；平台建议走 S2 轨道二 platform_insight 透明标注，两轨绝不混淆）。
"""

from __future__ import annotations

import json

from src.runtime.env_sources.base import EnvSourceBase


class BenchmarkSource(EnvSourceBase):
    name = "benchmark"
    kind = "benchmark"
    label = "行业智能化对标（官方名录）"
    credibility = "official"

    def _live_url(self) -> str:
        try:
            from src.common.config import settings

            return settings.env_benchmark_url or ""
        except Exception:
            return ""

    def _parse_live(self, text: str, limit: int) -> list[dict]:
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for it in items[:limit]:
            out.append({
                "title": str(it.get("title", it.get("company", "")))[:200],
                "content": str(it.get("content", it.get("highlight", "")))[:500],
                "category": "benchmark",
                "entities": [f"BENCH:{str(it.get('company', it.get('title','')))[:60]}"],
                "url": str(it.get("url", "")),
            })
        return [o for o in out if o["title"]]

    def _simulated_samples(self, limit: int) -> list[dict]:
        samples = [
            {
                "title": "新一批智能制造示范工厂名单发布（演示）",
                "content": "电子制造领域多家同行入选示范工厂，入选案例普遍实现排产决策分钟级响应与"
                           "设备综合效率（OEE）显著提升——行业智能化水位正在抬升。",
                "category": "benchmark",
                "entities": ["BENCH:智能制造示范工厂", "KPI:决策实时化率"],
                "url": "https://www.miit.gov.cn/（演示样本）",
            },
            {
                "title": "全球灯塔工厂新增名单要点（演示）",
                "content": "本批新增灯塔工厂中电子行业占比居前，标杆实践集中在 AI 排产、预测性维护与能碳一体化。",
                "category": "benchmark",
                "entities": ["BENCH:灯塔工厂", "IND:电子制造"],
                "url": "https://www.weforum.org/（演示样本）",
            },
            {
                "title": "制造业数字化转型指数区域报告（演示）",
                "content": "长三角/珠三角电子制造数字化渗透率继续领跑，中小企业智能化改造补贴申领窗口开放。",
                "category": "benchmark",
                "entities": ["BENCH:数字化转型指数", "POLICY:改造补贴"],
                "url": "官方公开报告（演示样本）",
            },
        ]
        return samples[:limit]
