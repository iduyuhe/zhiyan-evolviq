"""环境源④：上市企业公告披露（官方披露，credibility=official）——「研究案例」模式（§3.7）

🔴 研究案例模式（2026-07-29 杜总定调）：不等签约客户，直接以区域行业标杆上市企业（公开数据可获取）
为研究案例对象。对外以「某某行业·某某客户·某某公司」匿名呈现（本例简化为"某某通讯公司"），
实质上内部锚定一家真实上市公司（real_anchor）做公开数据推演。

live 模式：settings.env_disclosure_url 配置交易所/公告聚合 JSON 后自动升级（外部接口，按用户铁律不做 live 实测）。
simulated 模式：确定性演示样本（匿名化，不含真实公司名；real_anchor=中兴通讯（000063.SZ）已锚定，样本已对齐其公开披露主题：运营商集采中标 / 自研半导体器件 / 全球市场准入与合规）。

消费方：外圈 4 agent（executive_cockpit 战略画像 / supply_chain 供应链 / procurement_manage 采购对标 /
compliance_q 合规）——对外以匿名"某某通讯公司"呈现于孪生大屏体外感知 / /environment 信号与源列表。

🔴 匿名铁律：真实公司名/代码仅存 real_anchor（内部变量/研究笔记），绝不进入外发 payload
（CHANNEL_ENVIRONMENT / 孪生大屏 / /environment 任何接口均不得含真名）。

F4 可信治理：credibility=official（官方披露为锚）。
韧性铁律：任何网络/解析失败静默回退 simulated 样本，绝不阻断。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.runtime.env_sources.base import EnvSourceBase

logger = logging.getLogger(__name__)


class DisclosureSource(EnvSourceBase):
    name = "disclosure"
    kind = "disclosure"
    label = "某某通讯公司（研究案例·公开披露）"
    credibility = "official"
    tenant_facing = False   # 平台级研究案例源，不进租户订阅视图/不占免费额度
    internal_only = False  # 🔴 研究案例模式：对外匿名呈现（非 internal_only），真实锚定仅存 real_anchor
    real_anchor: str = "中兴通讯（000063.SZ）"  # 🔴 内部锚定真实上市公司（杜总 2026-07-29 确认）；绝不进入外发 payload/status

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
        # 对齐 中兴通讯（000063.SZ）公开披露主题：运营商集采中标 / 自研半导体器件 / 全球市场准入与合规
        samples = [
            {
                "title": "中标某运营商 5G 规模集采项目（演示）",
                "content": "公司公告中标某运营商 5G 规模集采项目，合同金额约 X 亿元，"
                           "预计对当年营收产生正向贡献，交付周期 18 个月；市场份额领先。",
                "category": "disclosure",
                "entities": ["DISC:运营商集采", "KPI:中标金额", "KPI:营收", "SUP:运营商"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
            {
                "title": "关于自研芯片及半导体器件取得进展的公告（演示）",
                "content": "公司披露自研基带/射频/交换芯片等半导体器件取得阶段性进展，"
                           "核心器件自供率提升，有望降低对外部供应链依赖并改善毛利结构。",
                "category": "disclosure",
                "entities": ["DISC:自研半导体", "KPI:毛利", "RAW:芯片", "SUP:供应链"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
            {
                "title": "关于全球市场准入与供应链合规的风险提示公告（演示）",
                "content": "公司提示部分海外市场准入与供应链合规存在不确定性，"
                           "已通过多区域产能布局与合规体系建设对冲相关风险，持续关注政策变化。",
                "category": "disclosure",
                "entities": ["DISC:合规", "POLICY:市场准入", "SUP:供应链", "RAW:地缘政治"],
                "url": "https://www.sse.com.cn/（演示样本）",
            },
        ]
        return samples[:limit]

    # ---- 发布：走共享通道 CHANNEL_ENVIRONMENT（对外匿名"某某通讯公司"呈现）----
    def publish_signal(self, signal: dict) -> Any:
        try:
            from src.runtime.uns import uns

            payload = dict(signal)
            # 🔴 匿名铁律：剥离任何可能携带真实公司名的字段，仅留匿名展示所需
            payload.pop("real_anchor", None)
            payload.pop("company", None)
            entities = payload.pop("entities", [])
            ev = uns.publish_environment(
                source=f"env://{self.kind}/{self.name}",
                payload=payload,
                entities=entities,
                type="env_signal",
                confidence=payload.pop("confidence", 1.0) if "confidence" in payload else 1.0,
                credibility=self.credibility,
            )
            return ev.id
        except Exception as e:
            logger.warning(f"⚠️ [{self.name}] 发布共享通道失败（不破管）：{e}")
            return None
