"""环境源②：原材料行情（官方指数，credibility=official）

live 模式：settings.env_market_url 配置官方指数接口后自动升级。
simulated 模式：确定性演示样本。
消费方：procurement_manage（采购）、supply_chain（供应链）。
"""

from __future__ import annotations

import json

from src.runtime.env_sources.base import EnvSourceBase


class MarketSource(EnvSourceBase):
    name = "market"
    kind = "market"
    label = "原材料行情（官方指数）"
    credibility = "official"

    def _live_url(self) -> str:
        try:
            from src.common.config import settings

            return settings.env_market_url or ""
        except Exception:
            return ""

    def _parse_live(self, text: str, limit: int) -> list[dict]:
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for it in items[:limit]:
            out.append({
                "title": str(it.get("title", it.get("name", "")))[:200],
                "content": str(it.get("content", it.get("value", "")))[:500],
                "category": "market",
                "entities": [f"MAT:{str(it.get('material', it.get('name','')))[:60]}"],
                "url": str(it.get("url", "")),
            })
        return [o for o in out if o["title"]]

    def _simulated_samples(self, limit: int) -> list[dict]:
        samples = [
            {
                "title": "电解铜现货均价周报（演示）",
                "content": "本周电解铜现货均价环比上行约2.1%，库存去化加快；铜箔/连接器物料成本承压，"
                           "建议关注远期合约锁价窗口。",
                "category": "market",
                "entities": ["MAT:电解铜", "KPI:采购成本"],
                "url": "https://www.shmet.com/（演示样本）",
            },
            {
                "title": "铝锭价格指数波动提示（演示）",
                "content": "铝锭指数近两周振幅扩大，结构件与散热件成本波动风险上升，建议双源备选评估。",
                "category": "market",
                "entities": ["MAT:铝锭", "SUP:双源备选"],
                "url": "https://www.smm.cn/（演示样本）",
            },
            {
                "title": "MLCC 主流料号供需简报（演示）",
                "content": "主流容值 MLCC 交期稳定、价格平稳，高容值料号交期小幅拉长，建议提前下达长交期物料订单。",
                "category": "market",
                "entities": ["MAT:CAP-001", "KPI:交期"],
                "url": "行业官方渠道（演示样本）",
            },
        ]
        return samples[:limit]
