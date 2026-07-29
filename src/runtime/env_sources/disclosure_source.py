"""环境源④：上市企业公告披露（官方披露，credibility=official）

live 模式：settings.env_disclosure_url 配置交易所/公告聚合 JSON 后自动升级（外部接口，按用户铁律不做 live 实测）。
simulated 模式：确定性演示样本（以轨道交通通信设备类上市公司公开披露方向为蓝本，仅演示用，不点名）。
消费方：executive_cockpit（战略）、supply_chain（供应链）、compliance_q（合规）。
用途：支撑「上铁通信研究型实证（§3.7）」——纯公开信号 → 企业经营画像 → 准且有价值的决策结论。

F4 可信治理：credibility=official（官方披露为锚）。
韧性铁律：任何网络/解析失败静默回退 simulated 样本，绝不阻断。
"""

from __future__ import annotations

import json

from src.runtime.env_sources.base import EnvSourceBase


class DisclosureSource(EnvSourceBase):
    name = "disclosure"
    kind = "disclosure"
    label = "上市企业公告披露（官方披露）"
    credibility = "official"
    tenant_facing = False  # 平台级研究源（上铁实证用），不进租户订阅视图/不占免费额度

    def _live_url(self) -> str:
        try:
            from src.common.config import settings

            return getattr(settings, "env_disclosure_url", "") or ""
        except Exception:
            return ""

    def _parse_live(self, text: str, limit: int) -> list[dict]:
        """约定 live 源返回 JSON 数组 [{title, content, company, ...}]；解析失败由基类回退 simulated。"""
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for it in items[:limit]:
            out.append({
                "title": str(it.get("title", ""))[:200],
                "content": str(it.get("content", it.get("summary", "")))[:500],
                "category": "disclosure",
                "entities": [f"DISC:{str(it.get('company', it.get('title', '')))[:60]}"],
                "url": str(it.get("url", "")),
            })
        return [o for o in out if o["title"]]

    def _simulated_samples(self, limit: int) -> list[dict]:
        samples = [
            {
                "title": "中标某城市轨道交通通信系统集成项目（演示）",
                "content": "公司公告中标某城市轨道交通通信系统集成项目，合同金额约 X 亿元，"
                           "预计对当年营收产生正向贡献，交付周期 18 个月。",
                "category": "disclosure",
                "entities": ["DISC:轨道交通装备", "KPI:中标金额", "SUP:城轨"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
            {
                "title": "关于原材料价格波动的风险提示公告（演示）",
                "content": "公司提示铜、铝等大宗原材料占成本比重较高，近期价格上行将阶段性挤压毛利，"
                           "已通过锁价与替代料验证对冲部分风险。",
                "category": "disclosure",
                "entities": ["DISC:原材料", "KPI:毛利", "RAW:铜", "RAW:铝"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
            {
                "title": "入选国家级专精特新「小巨人」企业名单（演示）",
                "content": "公司入选新一批国家级专精特新「小巨人」企业，将在研发补贴与招投标评分上获得政策支持。",
                "category": "disclosure",
                "entities": ["DISC:专精特新", "POLICY:小巨人", "KPI:政策补贴"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
        ]
        return samples[:limit]
