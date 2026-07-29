"""环境源④：上市企业公告披露（官方披露，credibility=official）——「研究案例」模式（§3.7）

🔴 研究案例模式（2026-07-29 杜总定调）：不等签约客户，直接以区域行业标杆上市企业（公开数据可获取）
为研究案例对象。对外以「某某行业·某某客户·某某公司」匿名呈现（本例简化为"某某通讯公司"），
实质上内部锚定一家真实上市公司（real_anchor）做公开数据推演。

live 模式：settings.env_disclosure_url 配置交易所/公告聚合 JSON 后自动升级（外部接口，按用户铁律不做 live 实测）。
simulated 模式：确定性演示样本（匿名化，不含真实公司名；real_anchor 给定后可对齐该真实公司公开披露节奏）。

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
    real_anchor: str = ""  # 🔴 内部锚定真实上市公司（由杜总指定后填充）；绝不进入外发 payload

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
