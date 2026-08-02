"""环境源⑤：客户声音情报（招投标/行业报告/客户舆情，credibility=authoritative）

第⑥路环境感知的「客户声音」维度落地（2026-08-02 方案 A：补全战略已定义、代码未落地的感知路，
不新增 Agent、不扩边缘）。客户声音是工业 B2B「商机情报 + 需求洞察」的公开数据形态——与 C 端营销
自动化不同，它的价值锚点是：客户在要什么（招投标）/ 客户的钱往哪走（资本开支）/ 客户在担心什么（舆情）。

live 模式：settings.env_customer_voice_url 配置招投标/行业报告/舆情聚合 JSON 后自动升级。
simulated 模式：确定性演示样本（对齐研究案例锚定行业=通讯：客户集采新需求 / 资本开支回暖 / 质量与交付关注）。

F4 可信治理：credibility=authoritative（非官方发布）→ 一律进 `_needs_review` 人工审核队列，
批准后才锚定（官方为锚、其余必筛红线）。消费方：外圈 5 agent（executive_cockpit / supply_chain /
procurement_manage / compliance_q / industry_research）经 env_context() 通道级自动受益。
韧性铁律：任何网络/解析失败静默回退 simulated 样本，绝不阻断。
"""

from __future__ import annotations

import json
import logging

from src.runtime.env_sources.base import EnvSourceBase

logger = logging.getLogger(__name__)


class CustomerVoiceSource(EnvSourceBase):
    name = "customer_voice"
    kind = "customer_voice"
    label = "客户声音（招投标/行业报告/舆情）"
    credibility = "authoritative"  # F4：非官方发布 → 人工审核队列，批准后才锚定

    def _live_url(self) -> str:
        try:
            from src.common.config import settings

            return settings.env_customer_voice_url or ""
        except Exception:
            return ""

    def _parse_live(self, text: str, limit: int) -> list[dict]:
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("items", [])
        out = []
        for it in items[:limit]:
            out.append({
                "title": str(it.get("title", ""))[:200],
                "content": str(it.get("content", it.get("summary", "")))[:500],
                "category": "customer_voice",
                "entities": [f"CUS:{str(it.get('customer', it.get('customer_type', '')))[:60]}"],
                "url": str(it.get("url", "")),
            })
        return [o for o in out if o["title"]]

    def _simulated_samples(self, limit: int) -> list[dict]:
        # 对齐研究案例锚定行业（通讯）：客户在要什么 / 客户的钱往哪走 / 客户在担心什么
        samples = [
            {
                "title": "某运营商发布新一轮集采招标：强调低时延与自主可控（演示）",
                "content": "客户集采招标文件显示，本批设备对低时延、自主可控提出明确评分要求，"
                           "交付窗口 12 个月。释放的需求信号：确定性交付能力 + 国产化方案将成为投标分水岭，"
                           "建议提前准备自主可控方案的性能对标数据。",
                "category": "customer_voice",
                "entities": ["CUS:运营商", "KPI:交付周期", "POLICY:自主可控"],
                "url": "行业招投标公开渠道（演示样本）",
            },
            {
                "title": "行业报告：下游客户资本开支进入回暖周期（演示）",
                "content": "多家头部客户的 5G/算力资本开支指引环比上调，采购窗口前移。"
                           "客户声音：设备选型更关注总拥有成本与能耗指标，报价策略应叠加能效分项。",
                "category": "customer_voice",
                "entities": ["CUS:算力客户", "KPI:资本开支", "KPI:能耗"],
                "url": "行业研究公开报告（演示样本）",
            },
            {
                "title": "客户舆情：某细分客户群体关注交付质量与售后响应（演示）",
                "content": "公开渠道客户反馈集中出现在交付质量稳定性与售后响应速度两个维度，"
                           "与竞品中标后口碑变化相关。建议外圈合规与供应链接入该信号，评估服务承诺条款风险。",
                "category": "customer_voice",
                "entities": ["CUS:行业客户", "KPI:交付质量", "KPI:售后响应"],
                "url": "公开舆情渠道（演示样本）",
            },
        ]
        return samples[:limit]
