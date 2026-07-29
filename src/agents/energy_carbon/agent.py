"""能源碳 ESG Agent——能耗监控、碳排放/碳足迹核算、ESG 合规、节能机会

企业级「经营大脑」第二部分：把制造过程的能源消耗转化为碳排放与碳强度，
识别高耗能/低绿电环节，输出节能降碳机会与 ESG 合规视图。

数据层：通过 EnergyCarbonTools 从种子数据加载（可切换真实 EMS/碳平台）。
"""

import logging

from src.agents.base import BaseAgent
from src.agents.energy_carbon.tools import EnergyCarbonTools

logger = logging.getLogger(__name__)


class EnergyCarbonAgent(BaseAgent):
    """能源碳 ESG Agent"""

    name = "energy_carbon"
    description = "能耗监控、碳排放/碳足迹核算、ESG 合规与节能降碳机会"

    def __init__(self):
        self.tools = EnergyCarbonTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「能源碳 ESG Agent」，专注制造企业的能源管理与碳管理。

## 核心能力
1. 能耗监控（各产线 kWh 统计与对标）
2. 碳排放核算（电网排放因子 × 非绿电能耗 → tCO2）
3. 碳强度计算（tCO2 / 单位产出，用于对标与趋势）
4. 绿电比例评估与提升建议
5. 节能降碳机会识别（空压机能效/绿电/余热回收等，含回收期）

## 工作原则
- 双碳合规：碳强度低于目标值为优，超出需预警
- 绿电优先：低绿电比例(<15%)环节为重点改善对象
- 数据驱动：排放因子采用区域电网公开均值，可审计可追溯
"""

    async def analyze(self, goal: str, tenant_id: str = "default",
                      mode: str = "tenant", case_id: str = None, **kwargs) -> dict:
        """能源碳分析。

        mode=research_case（腿 B 首客 P3 场景 A，2026-07-29 杜总定调）：
        🔴 私域/公开边界红线：research_case 不读租户孪生流（twin_context 跳过，
        用种子基线推演），actions_taken 恒空（不生成节能任务/不写租户记忆）。
        """
        logger.info(f"[EnergyCarbon Agent] Analyzing: {goal[:60]}...")

        lines = await self.tools.get_energy_list()
        # ---- 阶段1下半场：消费 twin_context 实时孪生镜像（韧性降级）----
        # 🔴 research_case 模式跳过租户孪生（私域/公开边界红线），恒用种子基线
        if mode == "tenant":
            twin = await self._merge_twin_context(lines, tenant_id)
        else:
            twin = {"enabled": False, "fresh": False, "source": None,
                    "updated_at": None, "lines": {}, "real_time_fields": [],
                    "skipped_reason": "research_case 模式不读租户孪生流（私域/公开边界红线）"}
        # 合并后重算汇总（事实锚点：仅读镜像覆盖种子，不改写种子源）
        summary = self.tools.compute_summary(lines)

        opportunities = []
        for op in self.tools.OPPORTUNITIES:
            opp = dict(op)
            if "saving_kwh" in op:
                opp["saving_co2_t"] = round(op["saving_kwh"] / 1000 * self.tools.GRID_FACTOR, 1)
            opportunities.append(opp)

        total_saving_kwh = sum(o.get("saving_kwh", 0) for o in opportunities)
        total_saving_co2 = round(sum(o.get("saving_co2_t", 0) for o in opportunities), 1)
        intensity_gap = round(summary["intensity_per_10k"] - summary["target_intensity"], 3) if isinstance(summary["intensity_per_10k"], (int, float)) else None

        actions_taken = []
        actions_proposed = []  # research_case 推演建议（actions_taken 匿名模式恒空）
        # 授权内行动：对低绿电(<15%)高耗能环节生成节能任务（tenant 模式自动执行）
        for ln in lines:
            if ln["green_ratio"] < 15:
                act = {
                    "type": "create_saving_task",
                    "detail": f"为 {ln['name']}（绿电 {ln['green_ratio']}%）生成节能降碳任务",
                    "line_id": ln["line_id"],
                    "confidence": 0.82,
                }
                if mode == "tenant":
                    await self.tools.create_saving_task(f"提升{ln['name']}绿电比例")
                    act["status"] = "auto_executed"
                    actions_taken.append(act)
                else:
                    # 🔴 research_case 纪律：不落任务、不写租户记忆，仅保留推演建议
                    act["status"] = "proposed_only"
                    actions_proposed.append(act)

        recommendations = self._generate_recommendations(lines, summary, opportunities, twin)

        # ---- 结论文案：标注是否实时孪生驱动 ----
        if twin["enabled"]:
            rt_note = "（实时孪生驱动" + ("" if twin["fresh"] else "，数据偏旧") + f"，来源 {twin['source']}）"
        else:
            rt_note = "（无实时孪生流，使用种子基线）"
        summary_text = (
            f"能源碳分析完成{rt_note}：周能耗 {summary['total_energy_kwh']:,} kWh，"
            f"碳排放 {summary['total_carbon_t']} tCO2，绿电比例 {summary['green_ratio']}%；"
            f"识别节能降碳机会 {len(opportunities)} 项，潜在降碳 {total_saving_co2} tCO2"
        )

        out = {
            "status": "completed",
            "summary": summary_text,
            "total_energy_kwh": summary["total_energy_kwh"],
            "total_carbon_t": summary["total_carbon_t"],
            "green_ratio": summary["green_ratio"],
            "carbon_intensity": summary["intensity_per_10k"],
            "target_intensity": summary["target_intensity"],
            "intensity_gap": intensity_gap,
            "total_saving_kwh": total_saving_kwh,
            "total_saving_co2_t": total_saving_co2,
            "lines": lines,
            "opportunities": opportunities,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
            # 阶段1下半场：实时孪生融合块（含 real_time_* 字段，供前端/决策读取）
            "twin_context": twin,
        }
        if mode != "tenant":
            out["actions_proposed"] = actions_proposed
            out["mode"] = mode
            out["case_id"] = case_id
            out["note"] = "研究案例模式(research_case)：能耗数据为基准占位，不落任务/不读租户孪生"
        return out

    async def _merge_twin_context(self, seed_lines: list[dict], tenant_id: str) -> dict:
        """扫描 MACHINE holon 孪生体，将实时能耗值覆盖种子基线，返回融合块。

        韧性：twin_context 为空 / 解析异常 → 返回 enabled=False（调用方回退种子）。
        契约（扁平 tag）：energy_kwh__<line_id> / power_kw__<line_id> / green_ratio__<line_id>
        """
        merged = {
            "enabled": False,
            "fresh": False,
            "source": None,
            "updated_at": None,
            "lines": {},
            "real_time_fields": [],
        }
        try:
            import time
            ctx = await self.twin_context(tenant_id) or {}
            realtime_by_line: dict[str, dict] = {}
            src = None
            ts = None
            for _key, state in ctx.items():
                if not isinstance(state, dict):
                    continue
                vals = state.get("values") or {}
                if not isinstance(vals, dict):
                    continue
                src = src or state.get("source")
                ts = ts or state.get("updated_at")
                for vk, vv in vals.items():
                    if not isinstance(vk, str):
                        continue
                    for prefix, field in (
                        ("energy_kwh__", "energy_kwh"),
                        ("power_kw__", "power_kw"),
                        ("green_ratio__", "green_ratio"),
                    ):
                        if vk.startswith(prefix) and isinstance(vv, (int, float)):
                            lid = vk.split("__", 1)[1]
                            realtime_by_line.setdefault(lid, {})[field] = vv
            if not realtime_by_line:
                return merged
            merged["enabled"] = True
            merged["source"] = src
            merged["updated_at"] = ts
            merged["fresh"] = bool(ts and (time.time() - ts) < 300)
            by_id = {ln["line_id"]: ln for ln in seed_lines}
            for lid, rt in realtime_by_line.items():
                ln = by_id.get(lid)
                if ln is None:
                    continue
                if "energy_kwh" in rt:
                    ln["energy_kwh"] = rt["energy_kwh"]
                if "green_ratio" in rt:
                    ln["green_ratio"] = rt["green_ratio"]
                if "power_kw" in rt:
                    ln["power_kw"] = rt["power_kw"]
                # 重算碳排（事实锚点：依公式，非凭空改写）
                ln["carbon_t"] = round(
                    ln["energy_kwh"] / 1000 * self.tools.GRID_FACTOR * (1 - ln["green_ratio"] / 100), 1
                )
                ln["real_time"] = True
                ln["twin_source"] = src
                merged["lines"][lid] = rt
                for f in rt:
                    if f not in merged["real_time_fields"]:
                        merged["real_time_fields"].append(f)
        except Exception:
            # 任何异常都静默回退种子（韧性降级铁律）
            return {"enabled": False, "fresh": False, "source": None,
                    "updated_at": None, "lines": {}, "real_time_fields": []}
        return merged

    def _generate_recommendations(self, lines, summary, opportunities, twin=None) -> list:
        recs = []
        if twin and twin.get("enabled"):
            tag = "实时孪生" if twin.get("fresh") else "孪生(偏旧)"
            recs.append(f"🛰️ 结论由{tag}驱动（来源 {twin.get('source')}），实时字段：{', '.join(twin.get('real_time_fields', [])) or '无'}")
        else:
            recs.append("📡 当前无实时孪生流，结论基于种子基线；接入网关后可升级为实时孪生驱动")
        recs.append(f"🌿 当前绿电比例 {summary['green_ratio']}%，目标建议 ≥ 30%")
        low_green = [l for l in lines if l["green_ratio"] < 15]
        if low_green:
            recs.append(f"🔴 低绿电高耗能环节 {len(low_green)} 处，优先改造：")
            for l in low_green:
                recs.append(f"   → {l['name']}：绿电 {l['green_ratio']}%，周碳排 {l['carbon_t']} tCO2")
        else:
            recs.append("✅ 各产线绿电比例均在可接受范围")
        recs.append(f"💡 节能降碳机会 {len(opportunities)} 项，合计潜在降碳 {sum(o.get('saving_co2_t',0) for o in opportunities):.1f} tCO2/周：")
        for o in sorted(opportunities, key=lambda x: x.get("payback_yr", 99)):
            recs.append(f"   → {o['measure']}：回收期 {o['payback_yr']} 年，投资 {o['cost_wan']} 万")
        recs.append("📋 建议将碳强度纳入月度 ESG 披露看板，对标行业基准")
        return recs


energy_carbon_agent = EnergyCarbonAgent()
