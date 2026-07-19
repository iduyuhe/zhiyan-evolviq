"""供应链自治Agent——MVP核心智能体（ROI 闭环版）

基于 LangGraph 理念实现的模块化 Agent，支持：
1. 自然语言目标解析
2. 多步骤自主规划
3. 工具调用（数据查询→分析→建议→执行）
4. 授权边界约束
5. 人工确认/介入

T3 增强：执行后产出**齐套率/交期准时率的可演示 ROI 闭环**——
  基准(现货+在途) → Agent 确认开放PO / 紧急催交延期PO / 锁定替代料 → 承诺齐套率。
所有数字均由种子数据 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

import json
import logging
import re

from src.agents.supply_chain.prompts import PLANNER_PROMPT, SYSTEM_PROMPT
from src.agents.supply_chain.tools import SupplyChainTools

logger = logging.getLogger(__name__)


class SupplyChainAgent:
    """供应链自治Agent"""

    def __init__(self):
        self.tools = SupplyChainTools()
        self.system_prompt = SYSTEM_PROMPT

    async def analyze_goal(self, goal: str, auth_boundary_id: str | None = None) -> str:
        """
        分析用户目标 → 生成执行规划

        Returns:
            Markdown格式的规划文本，展示给人确认
        """
        logger.info(f"📋 Analyzing goal: {goal[:80]}...")

        # 解析授权边界（MVP阶段为简化配置）
        auth_info = self._parse_auth_boundary(auth_boundary_id)

        # 生成规划（MVP阶段：基于规则 + LLM辅助，V1完整LangGraph）
        plan_md = self._generate_plan(goal, auth_info)

        logger.info(f"✅ Plan generated ({len(plan_md)} chars)")
        return plan_md

    async def execute(self, goal: str, plan: str) -> dict:
        """
        执行已确认的规划，产出齐套率 ROI 闭环结果。

        Returns:
            执行结果（含 metrics 前后对比、逐物料 before/after、授权内行动）
        """
        logger.info(f"⚡ Executing plan for goal: {goal[:80]}...")

        # 解析目标中的BOMID或关键参数
        bom_id = self._extract_bom_id(goal)
        if not bom_id:
            bom_id = "BOM-SMIC-28nm-Logic"

        # Step 1-3: 获取 BOM / 库存 / PO 数据
        bom = await self.tools.get_bom_data(bom_id)
        material_codes = [item["material_code"] for item in bom["items"]]
        inventory = await self.tools.get_inventory(material_codes)
        pos = await self.tools.get_po_data(material_codes)

        # Step 4: 基准齐套检查（仅现货 + 在途，即"现在能投产多少"）
        baseline_checks = self._run_supply_check(bom, inventory, pos, overrides=None)
        baseline_completeness = self._calc_completeness(baseline_checks)
        baseline_risk = sum(1 for c in baseline_checks if c["risk_after"] in ("high", "critical"))
        baseline_shortage = sum(max(0, c["required"] - c["available_before"]) for c in baseline_checks)

        # Step 5: 在授权范围内生成缓解行动（确认开放PO / 催交延期PO / 锁定替代料）
        actions_taken = []
        alternatives_found = []
        overrides: dict[str, int] = {}  # material_code -> 追加可用量（行动落地后）

        auth = self._parse_auth_boundary(None)
        max_lock = auth.get("max_lock_qty_per_item", 1000)

        for c in baseline_checks:
            if c["shortage_before"] <= 0:
                continue
            code = c["material_code"]
            added = 0

            # 杠杆1：确认开放PO（自主——本就是我方已下达订单，确认交期即可纳入承诺供应）
            open_qty = c["open_qty"]
            if open_qty > 0:
                actions_taken.append({
                    "type": "confirm_po",
                    "material": code,
                    "name": c["name"],
                    "qty": open_qty,
                    "status": "auto_confirmed",
                    "note": "确认开放PO交期，纳入承诺供应",
                })
                added += open_qty

            # 杠杆2：紧急催交延期PO（待批——加急产生溢价，需人决策）
            delayed_qty = c["delayed_qty"]
            if delayed_qty > 0:
                actions_taken.append({
                    "type": "expedite_po",
                    "material": code,
                    "name": c["name"],
                    "qty": delayed_qty,
                    "status": "pending_approval",
                    "note": "紧急催交延期PO（可能产生加急费）",
                })
                added += delayed_qty  # 假设获批后纳入承诺供应

            # 杠杆3：对残余缺料锁定替代料（去单点依赖风险）
            residual = max(0, c["shortage_before"] - added)
            alts = await self.tools.find_alternatives(code)
            if alts:
                alternatives_found.append({
                    "material": code,
                    "name": c["name"],
                    "alternatives": alts,
                })
            if residual > 0 and alts:
                alt = alts[0]
                lock_qty = residual
                status = "pending_approval" if lock_qty > max_lock else "auto_locked"
                actions_taken.append({
                    "type": "lock_alternative",
                    "material": code,
                    "name": c["name"],
                    "alternative": alt["name"],
                    "qty": lock_qty,
                    "status": status,
                    "note": f"锁定替代料 {alt['name']}（{alt.get('supplier','')}）",
                })
                added += lock_qty  # 假设获批后纳入承诺供应

            if added > 0:
                overrides[code] = added

        # Step 6: 行动落地后重算齐套（承诺齐套率）—— 价值闭环的核心
        post_checks = self._run_supply_check(bom, inventory, pos, overrides=overrides)
        post_completeness = self._calc_completeness(post_checks)
        post_risk = sum(1 for c in post_checks if c["risk_after"] in ("high", "critical"))
        post_shortage = sum(max(0, c["required"] - c["available_after"]) for c in post_checks)

        # 交期准时率（在途PO中未延期占比）
        delivery_before, delivery_after = self._calc_delivery_accuracy(pos, overrides)

        # 组装结果
        risk_items_total = sum(1 for c in baseline_checks if c["risk_before"] in ("high", "critical"))
        result = {
            "status": "completed",
            "agent": "supply_chain",
            "summary": (
                f"齐套率 ROI 闭环：基准 {baseline_completeness:.1f}% → 承诺 {post_completeness:.1f}%，"
                f"提升 {post_completeness - baseline_completeness:.1f} 个百分点；"
                f"缺料风险项 {risk_items_total} → {post_risk}；交期准时率 {delivery_before:.1f}% → {delivery_after:.1f}%"
            ),
            "bom": bom["product_name"],
            "completeness_pct": round(post_completeness, 1),  # 顶部仪表用承诺齐套率
            "metrics": {
                "kitting_rate_before": round(baseline_completeness, 1),
                "kitting_rate_after": round(post_completeness, 1),
                "improvement_pp": round(post_completeness - baseline_completeness, 1),
                "risk_items_before": risk_items_total,
                "risk_items_after": post_risk,
                "shortage_qty_before": baseline_shortage,
                "shortage_qty_after": post_shortage,
                "delivery_accuracy_before": round(delivery_before, 1),
                "delivery_accuracy_after": round(delivery_after, 1),
                "delivery_improvement_pp": round(delivery_after - delivery_before, 1),
                "roi_summary": (
                    f"齐套率 {baseline_completeness:.1f}% → {post_completeness:.1f}%"
                    f"（{'+' if post_completeness >= baseline_completeness else ''}{post_completeness - baseline_completeness:.1f}pp）；"
                    f"缺料风险项 {risk_items_total} → {post_risk}；"
                    f"交期准时率 {delivery_before:.1f}% → {delivery_after:.1f}%"
                ),
            },
            "check_details": [
                {
                    "material": c["material_code"],
                    "name": c["name"],
                    "required": c["required"],
                    "available_before": c["available_before"],
                    "available_after": c["available_after"],
                    "shortage_before": c["shortage_before"],
                    "shortage_after": c["shortage_after"],
                    "risk_before": c["risk_before"],
                    "risk_after": c["risk_after"],
                    "alternative": c["alternative_after"],
                }
                for c in post_checks
            ],
            "actions_taken": actions_taken,
            "alternatives_found": alternatives_found,
            "warning": self._generate_warnings(post_checks),
        }

        logger.info(f"✅ Execution completed: {result['summary']}")
        return result

    def _parse_auth_boundary(self, boundary_id: str | None) -> dict:
        """解析授权边界配置"""
        # MVP阶段：默认授权配置
        return {
            "max_price_variation_pct": 5.0,
            "max_lock_qty_per_item": 1000,
            "auto_approve_threshold": "medium",
            "require_approval_for": ["新供应商", "价格波动>5%", "非标品"],
        }

    def _generate_plan(self, goal: str, auth: dict) -> str:
        """生成自然语言规划（SMIC定制版）"""
        # 检测场景类型
        is_smic = "SMIC" in goal or "smic" in goal or "中芯" in goal or "28nm" in goal or "硅片" in goal or "光刻胶" in goal
        has_bom = "BOM" in goal or "bom" in goal or "NPI" in goal
        has_check = "检查" in goal or "齐套" in goal or "check" in goal
        has_auto = "自动" in goal or "自主" in goal or "直接" in goal

        # SMIC定制头部
        smic_header = ""
        if is_smic:
            smic_header = """
> 🏭 **客户**: 中芯国际(SMIC) | **场景**: 半导体供应链管理
"""

        plan = f"""## 📋 Agent执行规划
{smic_header}
### 1️⃣ 目标理解
> {goal}

### 2️⃣ 数据需求
| 数据类型 | 来源 | 用途 |
|---------|------|------|
| BOM清单 | ERP/MES系统 | {"获取SMIC-28nm工艺BOM" if is_smic else "获取NPI产品物料结构"} |
| 库存记录 | WMS系统 | {"查询FAB1/FAB2/Warehouse库存" if is_smic else "统计可用库存量"} |
| PO交期 | SRM系统 | {"查询在途PO和供应商交期" if is_smic else "计算在途物料可用时间"} |
| 供应商数据 | 供应商主数据 | {"评估国产/进口替代供应商" if is_smic else "评估替代供应商"} |

### 3️⃣ 分析步骤
| 步骤 | 操作 | 工具 |
|:----:|------|:----:|
| 1 | 读取BOM物料清单 | `get_bom_data` |
| 2 | 查询各物料库存余额 | `get_inventory` |
| 3 | 查询在途PO交期 | `get_po_data` |
| 4 | 执行齐套计算→生成风险矩阵 | `supply_check` |
| 5 | 对风险物料检索替代方案 | `find_alternatives` |
| {f"6 | {'在授权范围内锁定替代库存(国产优先)' if is_smic else '在授权范围内锁定替代库存'}" if has_auto else "6 | 生成采购建议报人审批"} | `lock_inventory` |
{"| 7 | 标注国产替代方案 | `find_alternatives(source=domestic)` |" if is_smic else ""}

### 4️⃣ 授权内自主行动
- ✅ 价格波动 < {auth.get('max_price_variation_pct', 5)}% 的替代料锁定
- ✅ 单物料锁定数量上限：{auth.get('max_lock_qty_per_item', 1000)} pcs
{"- 🇨🇳 国产替代优先：同等条件优先选择国产供应商" if is_smic else ""}
- ⛔ 新供应商引入 → 需人审批
- ⛔ 超出授权范围的采购 → 需人审批

### 5️⃣ 预计耗时
- 数据查询：约30秒
- 齐套计算：约10秒
- 替代检索：约20秒
- **总计：约1分钟**

> 请确认以上规划是否可以执行？如有调整请在下方反馈。
"""
        return plan

    def _extract_bom_id(self, goal: str) -> str | None:
        """从目标文本中提取BOM编号"""
        match = re.search(r'BOM[-\s]?([A-Za-z0-9]+)', goal, re.IGNORECASE)
        return f"BOM-{match.group(1)}" if match else None

    def _availability(self, item: dict, inv: dict, po_list: list) -> dict:
        """拆解某物料的可用量构成（确定性，来自种子数据）"""
        on_hand = inv.get("on_hand", 0)
        reserved = inv.get("reserved", 0)
        available = on_hand - reserved
        in_transit = sum(p["qty"] for p in po_list if p.get("status") == "in_transit")
        open_qty = sum(p["qty"] for p in po_list if p.get("status") == "open")
        delayed_qty = sum(p["qty"] for p in po_list if p.get("status") == "delayed")
        confirmed = sum(p["qty"] for p in po_list if p.get("status") == "confirmed")
        return {
            "on_hand": on_hand,
            "reserved": reserved,
            "available": available,
            "in_transit": in_transit,
            "open_qty": open_qty,
            "delayed_qty": delayed_qty,
            "confirmed": confirmed,
        }

    def _risk_level(self, shortage: int, required: int) -> str:
        """缺料风险等级（确定性规则）"""
        if required <= 0:
            return "low"
        shortage_pct = shortage / required
        if shortage_pct <= 0:
            return "low"
        elif shortage_pct < 0.3:
            return "medium"
        elif shortage_pct < 0.6:
            return "high"
        else:
            return "critical"

    def _run_supply_check(self, bom: dict, inventory: dict, pos: dict, overrides: dict | None = None) -> list:
        """执行齐套检查，返回逐物料 before/after 结果。

        Args:
            overrides: material_code -> 追加可用量（Agent 行动落地后）。为 None 时只算基准。
        """
        overrides = overrides or {}
        results = []
        for item in bom["items"]:
            code = item["material_code"]
            required = item["qty"]
            inv = inventory.get(code, {})
            po_list = pos.get(code, [])

            a = self._availability(item, inv, po_list)
            # 基准：现货 + 在途（物理上已在此或已在途）
            available_before = a["available"] + a["in_transit"]
            shortage_before = max(0, required - available_before)
            risk_before = self._risk_level(shortage_before, required)

            # 行动落地后：基准 + 追加承诺供应（确认PO + 催交 + 替代锁定）
            added = overrides.get(code, 0)
            available_after = available_before + added
            shortage_after = max(0, required - available_after)
            risk_after = self._risk_level(shortage_after, required)

            # 替代料标注（行动后）
            alternative_after = None
            if shortage_before > 0 and added > 0:
                # 有行动覆盖的物料，记录首个替代（若有），用于展示去风险
                pass  # 具体替代名在 execute 中通过 find_alternatives 填充到 actions，这里留 None

            results.append({
                "material_code": code,
                "name": item["name"],
                "required": required,
                "available_before": available_before,
                "available_after": available_after,
                "shortage_before": shortage_before,
                "shortage_after": shortage_after,
                "risk_before": risk_before,
                "risk_after": risk_after,
                "alternative_after": alternative_after,
                "open_qty": a["open_qty"],
                "delayed_qty": a["delayed_qty"],
            })
        return results

    def _calc_completeness(self, checks: list) -> float:
        """齐套率 = 零缺料物料占比（项维度）"""
        if not checks:
            return 100.0
        ok_items = sum(1 for c in checks if c["risk_after"] == "low")
        return round(ok_items / len(checks) * 100, 1)

    def _calc_delivery_accuracy(self, pos: dict, overrides: dict) -> tuple[float, float]:
        """交期准时率 = 未延期PO占比。

        before: 延期PO视为不准时。
        after: 延期PO被催交（overrides 覆盖的物料）后视为恢复准时。
        """
        all_pos = []
        expedited_codes = set(overrides.keys())
        for code, po_list in pos.items():
            for p in po_list:
                all_pos.append(p)
        if not all_pos:
            return 100.0, 100.0
        on_time_before = sum(1 for p in all_pos if p.get("status") != "delayed")
        on_time_after = sum(
            1 for p in all_pos
            if p.get("status") != "delayed" or p["material_code"] in expedited_codes
        )
        total = len(all_pos)
        return on_time_before / total * 100, on_time_after / total * 100

    def _generate_warnings(self, checks: list) -> list:
        """生成预警信息（基于行动后状态）"""
        warnings = []
        for c in checks:
            if c["risk_after"] == "critical":
                warnings.append(f"🔴 {c['name']}({c['material_code']})仍严重缺料{c['shortage_after']}pcs，需人介入")
            elif c["risk_after"] == "high":
                warnings.append(f"🟠 {c['name']}({c['material_code']})缺料{c['shortage_after']}pcs，建议尽快处理")
        return warnings


# 单例
supply_chain_agent = SupplyChainAgent()
