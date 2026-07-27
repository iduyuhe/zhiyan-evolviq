"""环境源①：政策法规（官方发布，credibility=official）

live 模式：settings.env_policy_url 配置官方发布页 JSON/RSS 后自动升级。
simulated 模式：确定性演示样本（真实存在的公开政策方向，仅演示用）。
消费方：compliance_q（合规）、executive_cockpit（战略）。
"""

from __future__ import annotations

import json

from src.runtime.env_sources.base import EnvSourceBase


class PolicySource(EnvSourceBase):
    name = "policy"
    kind = "policy"
    label = "政策法规（官方发布）"
    credibility = "official"

    def _live_url(self) -> str:
        try:
            from src.common.config import settings

            return settings.env_policy_url or ""
        except Exception:
            return ""

    def _parse_live(self, text: str, limit: int) -> list[dict]:
        """约定 live 源返回 JSON 数组 [{title, content, ...}]；解析失败由基类回退 simulated。"""
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for it in items[:limit]:
            out.append({
                "title": str(it.get("title", ""))[:200],
                "content": str(it.get("content", it.get("summary", "")))[:500],
                "category": "policy",
                "entities": [f"POLICY:{str(it.get('title',''))[:60]}"],
                "url": str(it.get("url", "")),
            })
        return [o for o in out if o["title"]]

    def _simulated_samples(self, limit: int) -> list[dict]:
        samples = [
            {
                "title": "智能制造试点示范行动申报通知（演示）",
                "content": "工信部组织开展新一批智能制造试点示范行动，聚焦离散制造数字化转型，"
                           "对入选企业给予政策与资金支持，申报截止本季度末。",
                "category": "policy",
                "entities": ["POLICY:智能制造试点示范", "IND:制造业"],
                "url": "https://www.miit.gov.cn/（演示样本）",
            },
            {
                "title": "工业能效提升行动计划要点（演示）",
                "content": "重点行业单位增加值能耗持续下降要求明确，电子制造企业需关注产线能耗监测与绿电占比指标。",
                "category": "policy",
                "entities": ["POLICY:工业能效提升", "KPI:能耗"],
                "url": "https://www.miit.gov.cn/（演示样本）",
            },
            {
                "title": "电子信息制造业稳增长指导意见（演示）",
                "content": "鼓励整机与元器件协同，支持关键材料国产替代，供应链安全被列为重点任务。",
                "category": "policy",
                "entities": ["POLICY:电子信息稳增长", "SUP:国产替代"],
                "url": "https://www.miit.gov.cn/（演示样本）",
            },
        ]
        return samples[:limit]
