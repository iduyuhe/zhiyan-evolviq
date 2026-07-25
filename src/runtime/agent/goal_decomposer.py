"""目标分解器（Goal Decomposer）——把一个复合目标拆成多个可分派给 Agent 的子目标。

设计原则：
1. **韧性降级（铁律）**：LLM 不可用 / 解析失败时自动回退到规则分解，绝不阻塞管道。
2. **预设场景模板**：常见综合场景预置模板，无 LLM 也能跑出多 Agent 协作。
3. **统一契约**：输出 `OrchestratorPlan`（data class），下游 orchestrator / engine 共用。

调用链：
    goal -> GoalDecomposer.decompose(goal) -> OrchestratorPlan
                                                  |
                                                  v
                                       Orchestrator.execute(plan)
                                                  |
                                                  v
                                       Orchestrator.aggregate(...)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Iterable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据契约
# ---------------------------------------------------------------------------


@dataclass
class SubTask:
    """编排计划中的一个子任务（一个 Agent 一次调用）"""
    task_id: str            # 子任务 ID（在 plan 内唯一，如 "t1"）
    agent: str              # 分派的 Agent 名（与 AGENT_REGISTRY 一致）
    sub_goal: str           # 派给该 Agent 的子目标描述
    focus: str = ""         # 该子任务在多 Agent 视图中的角色，如「主分析」「交叉验证」
    depends_on: list[str] = field(default_factory=list)  # 前置子任务 ID 列表
    parallel: bool = True   # 是否可并行（默认 True；depends_on 非空时由调度器决定）


@dataclass
class OrchestratorPlan:
    """多 Agent 编排计划"""
    goal: str                                    # 用户原始目标
    strategy: str = "parallel"                   # 编排策略：parallel / sequential / dag
    sub_tasks: list[SubTask] = field(default_factory=list)
    rationale: str = ""                          # 分解理由（展示给用户）
    source: str = "rule"                         # 分解来源：rule / llm / template

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "strategy": self.strategy,
            "rationale": self.rationale,
            "source": self.source,
            "sub_tasks": [asdict(t) for t in self.sub_tasks],
        }


# ---------------------------------------------------------------------------
# 预设场景模板（无需 LLM 也能跑）
# ---------------------------------------------------------------------------
# 触发条件：goal 中至少命中该模板的 1 个 trigger 关键词（不区分大小写）。
# 每个模板列出协同的 Agent 列表与各自的 sub_goal 模板。
# 编排理由（rationale）面向人解释"为什么要这几个 Agent 一起干"。


SCENARIO_TEMPLATES: list[dict] = [
    {
        "name": "新品导入完整评估",
        "triggers": ["新品导入", "npi", "新产", "新产品", "原型", "试产", "量产放行", "design review"],
        "agents": [
            ("dfm_check",     "对该新品的可制造性设计进行 DFM 审查，识别 PCB/封装/工艺风险"),
            ("bom_selector",  "为该新品做元器件选型，给出主选 + pin-to-pin 替代料清单"),
            ("rd_npi",        "评估 NPI 项目里程碑、批量试产准备度、研发-生产交接风险"),
            ("smt_changeover","为新品规划首件换线方案（料站/钢网/贴装程序）"),
            ("cost_analysis", "核算新品单位制造成本，给出报价支撑与降本空间"),
        ],
        "rationale": "新品导入是一条贯穿研发→工艺→供应链→成本的链路，单一 Agent 视角必然失真。"
                     "需要 DFM+BOM+NPI+换线+成本五个 Agent 串成完整评估闭环。",
    },
    {
        "name": "齐套率与交付改善",
        "triggers": ["齐套率", "齐套", "缺料", "交付", "交期", "不能按期", "工单延误", "未交付", "短料"],
        "agents": [
            ("supply_chain",  "分析缺料根因、给出替代料/补货建议"),
            ("demand_order",  "审视需求订单履约状态，识别高交期风险订单"),
            ("aps_scheduler", "重新排程，评估交期承诺的可执行性"),
            ("wms_logistics", "检查仓储/在途/呆滞，给出物料可调拨建议"),
            ("procurement_manage", "针对长交期物料给出供应商绩效与采购策略建议"),
        ],
        "rationale": "齐套问题往往不是单点缺料，而是需求-采购-排程-仓储四环共同作用。"
                     "五个 Agent 联合诊断能锁定是供应链源头问题还是排程承诺问题。",
    },
    {
        "name": "综合 OEE 提升",
        "triggers": ["oee", "综合效率", "产线效率", "可用率", "性能率", "换线效率", "六大损失"],
        "agents": [
            ("oee_optimizer",     "分析产线 OEE 六大损失分布，定位最大改善点"),
            ("smt_changeover",    "优化换线时间，缩短 setup 损失"),
            ("pm_maintenance",    "诊断设备健康，识别故障停机风险"),
            ("yield_analysis",    "分析良率损失，提出缺陷改善方向"),
            ("energy_carbon",     "从能耗维度给出非生产时段停机节能建议"),
        ],
        "rationale": "OEE 是可用率 × 性能率 × 良率 的乘积，任何单一 Agent 视角都会低估系统性损失。"
                     "五个 Agent 联合诊断能识别最大损失桶并给出协同改善方案。",
    },
    {
        "name": "能耗与碳排放治理",
        "triggers": ["能耗", "能源", "碳排放", "碳足迹", "esg", "双碳", "节能", "绿电", "减排"],
        "agents": [
            ("energy_carbon",     "核算产线/厂区能耗与碳排放，识别高耗能设备"),
            ("oee_optimizer",     "识别空载/低负载运行时段，挖掘节能空间"),
            ("cost_analysis",     "评估节能改造的 ROI，给出投资回收期"),
            ("compliance_q",      "对照 ISO 50001/ESG 披露要求，给出合规差距清单"),
        ],
        "rationale": "双碳目标不只是能源数字游戏，必须联动生产效率（避免为了节能停掉高产线）"
                     "、成本（节能改造要算账）、合规（披露要有依据）。",
    },
    {
        "name": "客户投诉与质量根因",
        "triggers": ["客诉", "投诉", "退货", "不良批次", "质量异常", "返修", "抱怨"],
        "agents": [
            ("quality_trace",     "从客诉批次反向追溯全链路，定位根因"),
            ("yield_analysis",    "分析同类缺陷的良率趋势，给出短期止血方案"),
            ("compliance_q",      "检查是否触发法规/体系上报义务，启动 CAPA"),
            ("ipc_standard",      "对照 IPC 标准判定缺陷等级与处置原则"),
            ("executive_cockpit", "给出客诉财务影响（退货成本+品牌损失+紧急工时）"),
        ],
        "rationale": "客诉不是质量部一个部门的事——质量追溯 + 良率止血 + 合规启动 + 财务评估"
                     "四件事必须并行做，缺一个都会让客诉升级。",
    },
    {
        "name": "经营驾驶舱综合决策",
        "triggers": ["经营", "驾驶舱", "kpi", "月报", "季度复盘", "预算执行", "利润分析", "经营决策"],
        "agents": [
            ("executive_cockpit", "拉通产销/人/钱/物的综合 KPI 看板"),
            ("cost_analysis",     "拆解制造成本结构，定位降本机会"),
            ("demand_order",      "分析订单履约与 S&OP 偏差，给出产销协同建议"),
            ("aps_scheduler",     "评估排程对产能利用率与交期的影响"),
            ("compliance_q",      "梳理合规风险敞口（质量/环保/安全/数据）"),
        ],
        "rationale": "经营决策不是看单点 KPI，而是产销人财物合规五维联动——"
                     "五个 Agent 联合输出才能支撑 CEO/CFO 级别的拍板。",
    },
    {
        "name": "工程变更影响分析",
        "triggers": ["eco", "ecn", "工程变更", "物料切换", "版本切换", "bom 变更", "工艺变更"],
        "agents": [
            ("eco_change",        "分析 ECO 影响范围（哪些产线/产品/订单受影响）"),
            ("bom_selector",      "对替换物料做兼容性 / 替代料评估"),
            ("dfm_check",         "评估变更对可制造性的影响"),
            ("aps_scheduler",     "安排变更切换窗口期与库存消化路径"),
            ("compliance_q",      "评估变更是否触发重新认证 / 客户通知义务"),
        ],
        "rationale": "一次 ECO 变更会同时影响工艺、供应链、计划、合规，单点评估必漏。",
    },
    {
        "name": "设备故障深度诊断",
        "triggers": ["故障", "停机", "维修", "设备异常", "报警", "维修后复发"],
        "agents": [
            ("pm_maintenance",    "诊断设备健康，预测维护窗口"),
            ("yield_analysis",    "评估故障对良率的累计影响"),
            ("quality_trace",     "检查是否已生产出受影响批次，启动追溯"),
            ("aoi_judge",         "过滤 AOI 误报，定位真实工艺偏移"),
        ],
        "rationale": "设备故障从来不是孤立的——它会立即反映在良率、批次质量、AOI 报警上，"
                     "四个 Agent 联合诊断能避免「修了又复发」。",
    },
]


# ---------------------------------------------------------------------------
# 规则分解器（兜底，无 LLM 也能工作）
# ---------------------------------------------------------------------------

# 关键词 → Agent 列表（用于无模板命中时的关键词聚合兜底）
# 注意：与 router.py 的 ROUTING_RULES 不同，这里会**聚合所有命中**的 Agent，而非返回第一个。
KEYWORD_TO_AGENTS: list[tuple[list[str], list[str]]] = [
    (["物料", "齐套", "缺料", "bom", "采购", "供应", "库存", "po"], ["supply_chain"]),
    (["选型", "替代料", "pin-to-pin", "兼容", "元器件"], ["bom_selector"]),
    (["dfm", "可制造性", "焊盘", "线宽", "阻焊", "过孔"], ["dfm_check"]),
    (["oee", "产线效率", "可用率", "性能率", "综合效率", "六大损失"], ["oee_optimizer"]),
    (["换线", "changeover", "smt", "料站", "feeder", "钢网"], ["smt_changeover"]),
    (["eco", "ecn", "变更", "工程变更", "物料切换"], ["eco_change"]),
    (["aoi", "误报", "复判", "光学检测"], ["aoi_judge"]),
    (["追溯", "trace", "客诉", "投诉", "根因", "root cause"], ["quality_trace"]),
    (["ipc", "标准", "判定", "class 1", "class 2", "class 3", "桥连", "焊点"], ["ipc_standard"]),
    (["良率", "yield", "缺陷", "defect", "颗粒", "污染", "合格率"], ["yield_analysis"]),
    (["设备", "维护", "保养", "故障", "光刻机", "刻蚀机", "备件", "健康"], ["pm_maintenance"]),
    (["排程", "排产", "生产计划", "产能", "工单", "aps", "scheduling"], ["aps_scheduler"]),
    (["需求", "订单", "接单", "未交付", "交期风险", "s&op", "forecast", "backlog"], ["demand_order"]),
    (["仓储", "仓库", "库容", "补货", "呆滞", "物流", "在途", "wms", "周转"], ["wms_logistics"]),
    (["能耗", "能源", "碳", "碳排放", "esg", "双碳", "节能", "绿电"], ["energy_carbon"]),
    (["成本", "制造成本", "降本", "报价", "毛利", "单位成本"], ["cost_analysis"]),
    (["合规", "认证", "iso", "审核", "rohs", "reach", "capa"], ["compliance_q"]),
    (["经营", "驾驶舱", "kpi", "看板", "预算", "利润", "营收", "现金流"], ["executive_cockpit"]),
    (["npi", "新产", "新产品导入", "里程碑", "试产", "量产放行"], ["rd_npi"]),
    (["供应商绩效", "合同到期", "竞价", "srm", "战略采购", "供应商管理"], ["procurement_manage"]),
]


def _match_templates(goal: str) -> list[dict]:
    """按 trigger 关键词命中预设场景模板。返回所有命中模板（去重）。"""
    g = goal.lower()
    matched: list[dict] = []
    for tpl in SCENARIO_TEMPLATES:
        for kw in tpl["triggers"]:
            if kw.lower() in g:
                matched.append(tpl)
                break
    return matched


def _aggregate_agents(goal: str) -> list[tuple[str, str]]:
    """按关键词聚合兜底：返回 [(agent_name, sub_goal_template), ...]"""
    g = goal.lower()
    agents: list[tuple[str, str]] = []
    seen: set[str] = set()
    for kws, ags in KEYWORD_TO_AGENTS:
        if any(kw.lower() in g for kw in kws):
            for a in ags:
                if a not in seen:
                    seen.add(a)
                    # 默认子目标：直接复用原 goal，Agent 内部按自身能力拆解
                    agents.append((a, goal))
    return agents


def _rule_decompose(goal: str) -> OrchestratorPlan:
    """规则化分解（兜底）。优先匹配场景模板；否则按关键词聚合。"""
    templates = _match_templates(goal)
    if templates:
        # 命中模板：合并所有模板涉及的 Agent（去重）
        merged: dict[str, str] = {}     # agent -> sub_goal
        for tpl in templates:
            for ag, sub in tpl["agents"]:
                merged[ag] = sub
        sub_tasks: list[SubTask] = []
        for i, (ag, sub) in enumerate(merged.items(), 1):
            sub_tasks.append(SubTask(
                task_id=f"t{i}",
                agent=ag,
                sub_goal=sub,
                focus="协同分析",
            ))
        names = " / ".join(t["name"] for t in templates)
        return OrchestratorPlan(
            goal=goal,
            strategy="parallel",
            sub_tasks=sub_tasks,
            rationale=f"命中预设场景模板：{names}。已合并所有相关 Agent 并行诊断。",
            source="template",
        )

    # 关键词聚合兜底
    pairs = _aggregate_agents(goal)
    if not pairs:
        # 真的无任何匹配：回退到单 Agent 默认
        pairs = [("supply_chain", goal)]
    sub_tasks = [
        SubTask(task_id=f"t{i+1}", agent=ag, sub_goal=sub, focus="协同分析")
        for i, (ag, sub) in enumerate(pairs)
    ]
    return OrchestratorPlan(
        goal=goal,
        strategy="parallel",
        sub_tasks=sub_tasks,
        rationale=("未命中预设场景模板；已根据关键词聚合相关 Agent 并行处理。"
                   f"共 {len(sub_tasks)} 个 Agent 参与。"),
        source="rule",
    )


# ---------------------------------------------------------------------------
# LLM 增强分解器（升级路径）
# ---------------------------------------------------------------------------

# LLM 输出 JSON 模板（prompt 内嵌）
_LLM_DECOMPOSE_PROMPT = """你是工业智能体编排器。请把用户的复合目标分解为可并行执行的子任务，每个子任务指派一个 Agent。

可用 Agent 列表（name: 能力）：
{dfm_check}: PCB 可制造性设计审查
{bom_selector}: 元器件选型与替代料
{rd_npi}: 新产品导入与试产
{smt_changeover}: SMT 换线优化
{oee_optimizer}: 产线 OEE 优化
{pm_maintenance}: 设备健康与维护
{yield_analysis}: 良率与缺陷分析
{quality_trace}: 客诉追溯与根因
{ipc_standard}: IPC 标准判定
{aoi_judge}: AOI 误报过滤
{eco_change}: 工程变更影响分析
{supply_chain}: 供应链与齐套
{demand_order}: 需求订单与 S&OP
{aps_scheduler}: 排程与产能
{wms_logistics}: 仓储物流
{energy_carbon}: 能耗与碳排放
{cost_analysis}: 制造成本
{compliance_q}: 质量合规与认证
{executive_cockpit}: 经营 KPI 驾驶舱
{procurement_manage}: 供应商管理

用户目标：{goal}

请用 JSON 格式输出（不要任何额外说明文字）：
{{
  "sub_tasks": [
    {{"agent": "<agent_name>", "sub_goal": "<该 Agent 要回答的子问题>", "focus": "<角色说明>"}}
  ],
  "rationale": "<为什么需要这几个 Agent 协作>"
}}

要求：
1. 至少 2 个 Agent，最多 6 个；优先选彼此互补的视角。
2. sub_goal 要具体，不能只是重复原目标。
3. rationale 解释为什么不能由单一 Agent 完成。
"""


async def _llm_decompose(goal: str) -> OrchestratorPlan | None:
    """LLM 增强分解。失败时返回 None，调用方回退到规则分解。"""
    try:
        from src.common.llm_client import llm_client
        if not llm_client.available:
            return None
        # 填充 prompt 模板（agent 名作为占位符，刻意写两次同名占位符以避免被替换冲突）
        prompt = _LLM_DECOMPOSE_PROMPT
        # 简化：直接给 LLM 一个"已知 Agent 列表"的硬编码片段，不再做替换
        from src.runtime.agent.router import AGENT_REGISTRY
        agent_list_text = "\n".join(
            f"- `{name}`: {AGENT_REGISTRY[name][0].split('.')[-2]}"  # 用模块名兜底描述
            for name in AGENT_REGISTRY
        )
        prompt = prompt.replace("{dfm_check}", "`dfm_check`")
        prompt = prompt.replace("{bom_selector}", "`bom_selector`")
        # ... 为简洁，对每个 agent name 走一遍替换
        for name in AGENT_REGISTRY:
            prompt = prompt.replace("{" + name + "}", f"`{name}`")
        prompt = prompt.replace("{goal}", goal)
        prompt_full = prompt.replace(
            "可用 Agent 列表（name: 能力）：\n-",
            "可用 Agent 列表（name: 能力）：\n" + agent_list_text + "\n\n补充参考：\n-",
        )

        raw = await llm_client.client.chat(prompt_full)  # 简化：直接走 chat
        # 实际项目里应该用结构化输出；这里兜底解析 JSON
        import json
        # 截取最外层 {...}
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            logger.warning("[LLM Decompose] No JSON block found in LLM output")
            return None
        data = json.loads(m.group(0))
        subs = data.get("sub_tasks") or []
        if not subs or not isinstance(subs, list):
            return None
        sub_tasks: list[SubTask] = []
        for i, s in enumerate(subs[:6], 1):
            ag = (s.get("agent") or "").strip()
            if ag not in AGENT_REGISTRY:
                logger.warning(f"[LLM Decompose] Skipping unknown agent: {ag}")
                continue
            sub_tasks.append(SubTask(
                task_id=f"t{i}",
                agent=ag,
                sub_goal=(s.get("sub_goal") or goal).strip(),
                focus=(s.get("focus") or "协同分析").strip(),
            ))
        if len(sub_tasks) < 2:
            return None
        return OrchestratorPlan(
            goal=goal,
            strategy="parallel",
            sub_tasks=sub_tasks,
            rationale=(data.get("rationale") or "").strip() or "由 LLM 编排器分解。",
            source="llm",
        )
    except Exception as e:
        logger.warning(f"[LLM Decompose] failed: {e}")
        return None


# ---------------------------------------------------------------------------
# 顶层入口
# ---------------------------------------------------------------------------


class GoalDecomposer:
    """目标分解器：自动选择 LLM 增强 / 规则 / 模板。

    调用方式：
        plan = await GoalDecomposer().decompose(goal)
    """

    async def decompose(self, goal: str) -> OrchestratorPlan:
        """异步入口。LLM 优先；失败/无 LLM 时回退到规则。"""
        # 1. 模板优先（成本低、可解释）
        tpl_match = _match_templates(goal)
        # 2. LLM 增强：仅在「无明确模板」时启用，避免 LLM 改写已稳定的预设
        if not tpl_match:
            llm_plan = await _llm_decompose(goal)
            if llm_plan is not None:
                return llm_plan
        # 3. 规则兜底（必到）
        return _rule_decompose(goal)

    def decompose_sync(self, goal: str) -> OrchestratorPlan:
        """同步入口：仅规则路径（用于测试 / 离线场景）。"""
        return _rule_decompose(goal)
