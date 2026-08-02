"""商机情报 Agent（bid_intel，2026-08-02 第 25 个 Agent，杜总拍板扩边缘）

营销向智能体实体化：工业 B2B 的「营销」= 商机情报（与 C 端增长漏斗完全不同）。
本 Agent 消费第⑥路环境感知的客户声音(customer_voice) + 竞品对标(benchmark) +
原材料行情(market) 三类信号，输出：
- 商机扫描（客户在要什么：招投标/需求信号）
- 竞品对标（对手在干什么：benchmark 信号）
- 市场/成本锚（行情信号 → 报价成本锚点）
- 赢单概率评估（确定性规则：信号强度 × 竞争烈度 × 自主可控匹配）
- 报价策略建议（结合市场成本锚点）
- 标前评审清单（go/no-go 前检查）

🔴 不自动执行商务动作（不代发标书/不自动报价）：情报分析 + 人留终审，
符合项目「人留终审」价值观与商务动作高风险属性。actions_taken 恒为空。
🔴 research_case 模式：不写租户作用域记忆、不执行行动，匿名推演。
🔴 事实锚点：所有数字/判断均来自 env_context 信号溯源（source URL + credibility），
不凭空捏造商机数据；信号为空时诚实输出「暂无信号」而非编造。
"""

from __future__ import annotations

import logging

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# 商机情报关注的信号类别（第⑥路营销向三源）
_SIGNAL_CATEGORIES = ("customer_voice", "benchmark", "market")

# 竞争烈度关键词（用于赢单概率的确定性规则；benchmark 信号内容命中即视为高竞争）
_COMPETITION_HINTS = ("中标", "份额", "领先", "竞争", "对比", "对标", "取代", "降价")
# 自主可控/差异化关键词（命中即视为我方优势锚点）
_ADVANTAGE_HINTS = ("自主可控", "国产化", "低时延", "能耗", "自研", "能效")


class BidIntelAgent(BaseAgent):
    """商机情报 Agent（第 25 个）——标前评审/赢单概率/竞品对标/报价策略"""

    name = "bid_intel"
    description = "商机情报：标前评审、赢单概率、竞品对标、报价策略 —— 工业 B2B 营销决策"

    def __init__(self) -> None:
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「商机情报 Agent」，制造企业 B2B 营销决策助手。

## 核心能力
1. 商机扫描：从客户声音（招投标/行业报告/舆情）识别在途商机与需求信号
2. 竞品对标：从行业对标信号评估竞争烈度与我方差异化锚点
3. 市场/成本锚：从原材料行情信号建立报价成本锚点
4. 赢单概率评估：基于信号强度、竞争烈度、差异化匹配的确定性规则推演
5. 报价策略建议：结合成本锚点与竞争格局给出报价区间思路
6. 标前评审清单：go/no-go 前的关键检查项

## 工作原则
- 情报驱动：所有判断来自环境感知信号（source URL + credibility 溯源），绝不编造商机
- 人留终审：只输出分析与建议，不自动执行任何商务动作（不发标书/不自动报价）
- 诚实优先：信号为空时如实说明，不用占位数据冒充真实情报
- 数字说话：赢单概率为确定性规则推演值，标注推导依据而非黑盒
"""

    async def analyze(self, goal: str, mode: str = "tenant", case_id: str = None) -> dict:
        logger.info(f"[BidIntel Agent] Analyzing: {goal[:60]}... (mode={mode})")

        # 环境感知：客户声音 + 竞品对标 + 市场行情（营销向三源）
        env = await self.env_context(limit=50)
        signals = env.get("signals", [])
        by_cat: dict[str, list[dict]] = {c: [] for c in _SIGNAL_CATEGORIES}
        for s in signals:
            cat = s.get("payload", {}).get("category", "")
            if cat in by_cat:
                by_cat[cat].append(s)

        voice = by_cat["customer_voice"]
        bench = by_cat["benchmark"]
        mkt = by_cat["market"]

        # 商机扫描：客户声音 → 商机信号
        opportunities = self._extract_opportunities(voice)

        # 竞品对标：benchmark 信号 + 竞争烈度判定
        competitive = self._extract_competitive(bench)

        # 市场/成本锚
        cost_anchor = self._extract_cost_anchor(mkt)

        # 赢单概率（确定性规则）
        win = self._estimate_win_probability(opportunities, competitive, cost_anchor)

        # 报价策略
        pricing = self._suggest_pricing(win, cost_anchor, competitive)

        # 标前评审清单
        bid_review = self._build_bid_review(win, competitive, cost_anchor)

        recommendations = self._generate_recommendations(
            opportunities, competitive, cost_anchor, win, pricing
        )

        return {
            "status": "completed",
            "summary": (
                f"商机情报完成：捕获 {len(opportunities)} 个商机信号、"
                f"{len(competitive)} 条竞品对标、{len(cost_anchor)} 条市场行情；"
                f"综合赢单概率 {win['score']}%（{win['grade']}）"
            ),
            "opportunities": opportunities,
            "competitive_benchmarks": competitive,
            "market_context": cost_anchor,
            "win_probability": win,
            "pricing_strategy": pricing,
            "bid_review": bid_review,
            "recommendations": recommendations,
            "actions_taken": [],  # 🔴 人留终审：情报分析不自动执行商务动作
            "env_signals": signals,
            "env_signal_count": env.get("count", 0),
            "mode": mode,
            "case_id": case_id,
            **({"note": "研究案例模式(research_case)：商机推演基于公开信号基准占位，不写租户作用域记忆；真实锚定仅内部可见"} if mode == "research_case" else {}),
        }

    # ---------- 确定性规则推演（事实锚点：全部来自 env 信号溯源） ----------

    def _extract_opportunities(self, voice: list[dict]) -> list[dict]:
        out = []
        for s in voice:
            p = s.get("payload", {})
            out.append({
                "title": p.get("title", "")[:200],
                "content": p.get("content", "")[:400],
                "customer": p.get("entities", []),
                "source": s.get("source", ""),
                "url": p.get("url", ""),
                "credibility": s.get("credibility", ""),
            })
        return out

    def _extract_competitive(self, bench: list[dict]) -> list[dict]:
        out = []
        for s in bench:
            p = s.get("payload", {})
            text = f"{p.get('title', '')} {p.get('content', '')}"
            out.append({
                "title": p.get("title", "")[:200],
                "content": p.get("content", "")[:400],
                "high_competition": any(h in text for h in _COMPETITION_HINTS),
                "advantage_hint": any(h in text for h in _ADVANTAGE_HINTS),
                "source": s.get("source", ""),
                "url": p.get("url", ""),
            })
        return out

    def _extract_cost_anchor(self, mkt: list[dict]) -> list[dict]:
        out = []
        for s in mkt:
            p = s.get("payload", {})
            out.append({
                "title": p.get("title", "")[:200],
                "content": p.get("content", "")[:400],
                "material": p.get("entities", []),
                "source": s.get("source", ""),
                "url": p.get("url", ""),
            })
        return out

    def _estimate_win_probability(self, opps: list[dict], comp: list[dict], mkt: list[dict]) -> dict:
        """确定性规则：信号强度(0.4) × 竞争烈度(0.35) × 差异化/成本锚(0.25)，基线 50。"""
        signal_score = min(40, 15 + 8 * len(opps))          # 有商机信号即有基础分
        comp_score = 30
        for c in comp:
            if c.get("high_competition"):
                comp_score -= 6                              # 竞争烈度高 → 扣分
            if c.get("advantage_hint"):
                comp_score += 4                              # 我方差异化锚 → 加分
        comp_score = max(10, min(30, comp_score))
        cost_score = 20
        if mkt:
            cost_score += 2                                  # 有行情锚 → 报价有据可依
        total = signal_score + comp_score + cost_score
        score = max(20, min(95, total))
        grade = "高" if score >= 70 else ("中" if score >= 50 else "低")
        return {
            "score": score,
            "grade": grade,
            "basis": {
                "signal_score": signal_score,
                "competition_score": comp_score,
                "cost_anchor_score": cost_score,
                "note": "确定性规则推演（非模型黑盒）：信号强度 40% + 竞争烈度 35% + 成本锚 25%",
            },
        }

    def _suggest_pricing(self, win: dict, mkt: list[dict], comp: list[dict]) -> dict:
        pressure = sum(1 for c in comp if c.get("high_competition"))
        suggestion = []
        if pressure >= 2:
            suggestion.append("竞争烈度高：报价侧重「总拥有成本/能效」差异化分项，避免纯价格战")
        elif pressure == 1:
            suggestion.append("存在主要竞争者：报价给出分级方案（标准/增强），用交付确定性换溢价")
        else:
            suggestion.append("竞争压力低：可按成本锚 + 目标毛利定价，留商务谈判余量")
        if mkt:
            suggestion.append("原材料行情有波动信号：建议报价条款含成本联动或锁价窗口")
        return {
            "competition_pressure": pressure,
            "win_grade": win["grade"],
            "suggestions": suggestion,
            "note": "报价为策略建议，最终报价须经人留终审（本 Agent 不自动执行）",
        }

    def _build_bid_review(self, win: dict, comp: list[dict], mkt: list[dict]) -> list[str]:
        items = []
        items.append(f"🟢 赢单概率 {win['score']}%（{win['grade']}）：{win['basis']['note']}")
        if comp:
            high = [c for c in comp if c.get("high_competition")]
            items.append(f"🟡 竞品对标 {len(comp)} 条，其中高竞争信号 {len(high)} 条")
            if high:
                items.append(f"   → 建议复核：{'、'.join(h['title'][:30] for h in high[:3])}")
        else:
            items.append("⚪ 暂无竞品对标信号：建议配置 benchmark 源或补充行业对标")
        if mkt:
            items.append(f"🔵 市场行情 {len(mkt)} 条：报价前复核成本锚点（{'、'.join(m['title'][:20] for m in mkt[:2])}）")
        else:
            items.append("⚪ 暂无行情信号：报价成本锚需人工补充")
        items.append("⚖️ go/no-go 检查：客户付款能力 / 交付产能 / 合规准入三项人工复核后提交")
        return items

    def _generate_recommendations(
        self, opps: list[dict], comp: list[dict], mkt: list[dict], win: dict, pricing: dict
    ) -> list[str]:
        recs = []
        if opps:
            recs.append(f"🎯 捕获 {len(opps)} 个客户声音信号，建议优先跟进：")
            for o in opps[:3]:
                recs.append(f"   → {o['title'][:50]}")
        else:
            recs.append("📭 暂无客户声音信号——请在 /environment 拉取 customer_voice 源或配置真实 URL")
        if comp:
            recs.append(f"🆚 {len(comp)} 条竞品对标已纳入竞争烈度评估（高竞争 {sum(1 for c in comp if c['high_competition'])} 条）")
        if mkt:
            recs.append(f"💰 {len(mkt)} 条行情信号已纳入成本锚：报价前复核物料成本走势")
        recs.extend(f"💡 {s}" for s in pricing["suggestions"])
        recs.append("🔒 商机情报不自动执行商务动作：投标/报价均须人留终审确认")
        return recs


bid_intel_agent = BidIntelAgent()
