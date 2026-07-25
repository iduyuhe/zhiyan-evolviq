# 记忆与自进化能力 — 架构与路线

> 对应评估表「多 Agent 编排 / 上手门槛」之外的第三维能力盘点。
> 本文档说明平台当前**记忆（Memory）**与**自学习（Self-Learning）**的真实状态、P0 已闭合的缺口，以及 P1/P2 演进路线。

## 1. 结论速览

| 能力 | 状态 | 说明 |
|------|------|------|
| 共享事实记忆（图谱） | ✅ 有 | Neo4j 语义网，跨 Agent 共享实体/关系 |
| 经验记忆写回（Insight） | ✅ **P0 已闭合** | 每次执行 / 编排的洞察落为 Insight 节点 |
| 推理时读回记忆（Recall） | ✅ **P0 已闭合** | `BaseAgent.recall(goal)` + `/kg/recall`，agent 带记忆推理 |
| 效果指标 / 审计持久化 | ✅ **P0 已闭合** | SQLite 落库 + 启动回灌，重启不丢 |
| 人类反馈→偏好/禁忌记忆 | ✅ **P1 已闭合** | 介入中心审批/驳回自动沉淀为 `FeedbackRecord`，供 recall 与策略反哺 |
| 规则自学习闭环（自动调参） | ✅ **P1 已闭合** | `strategy_tuner.auto_tune()` 带护栏自动应用 + 一键回滚 |
| 自进化（Prompt/知识自修订） | 🔴 P2（远景） | 反思循环修订 prompt / RAG 自更新 / 偏好学习 |

## 2. 记忆架构（P0 后）

```
Agent 执行 / 多 Agent 编排
        │  apply_execution_result / apply_orchestration_result
        ▼
知识图谱（Neo4j / 内存图双模式）
        │  写入 Insight 节点（跨 Agent 经验）+ 结构化实体更新
        ▼
BaseAgent.recall(goal)  ──►  /kg/recall API
        │  CJK n-gram 相关度排序，按租户隔离
        ▼
下次推理带「历史经验」上下文  ──►  产出新结论  ──►  再次写回（闭环）
```

### 2.1 经验记忆载体：`Insight` 节点

- 任何 Agent 的 `result["summary"]` / `result["insights"]` 自动落为 `Insight` 节点（`source="execution"`）。
- 多 Agent 编排的 `cross_findings`（跨域洞察）与 `priority_actions`（优先级动作）落为 `Insight` 节点（`source="orchestration"` / `"orchestration_action"`）。
- 所有节点带 `tenant` 属性 → 多租户隔离，互不可见。
- 事实锚点铁律：仅写实体/关系/经验文本，绝不改写任何业务数字。

### 2.2 召回：`MemoryStore`

- `src/runtime/memory.py` 的 `recall(goal, tenant_id, limit)`：查询本租户 Insight 节点，按 CJK 二元/三元 n-gram 重叠度排序，返回最相关经验。
- 纯启发式、零 LLM、低延迟、确定性；图谱不可用时安全返回空。
- `BaseAgent.recall()` 默认实现即包此函数，agent 可在 `analyze()` 内主动调用；编排器在每子任务推理前自动召回并注入上下文。

### 2.3 持久化

- 效果指标（`metrics`）与审计（`audit`）经 `persistence` 落 SQLite（resilience 回退），启动时空 `hydrate()` 回灌内存 → 效果信号跨重启累积，支撑「按效果调参」基于真实历史。

## 3. 修复的关键缺口

| 缺口 | 现象 | 修复 |
|------|------|------|
| 编排洞察丢失 | `engine.execute_multi` 从未调用 `apply_orchestration_result`，跨域洞察静默消失 | 实现并接线，返回前 `await` 落库 |
| 执行记忆窄 | `apply_execution_result` 仅覆盖 2 个 agent 的 2 种动作 | 扩展至全部 20 agent（通用 Insight + 结构化增量） |
| 记忆不回灌 | agent 推理时不读 KG（`src/agents` 零调用） | `recall` 钩子 + 编排器集成 |
| 信号重启即丢 | metrics/audit 纯内存 | SQLite 落库 + 启动回灌 |

## 4. P1 — 规则自学习闭环（2026-07-25 已闭合）

把「人类反馈」与「自动调参」接成闭环，使平台从「执行机器 + 人工调参面板」升级为「能从人类决策中持续学习、并带护栏自动优化」的系统。

### 4.1 人类反馈 → 偏好/禁忌记忆

- `src/runtime/experience.py` 的 `ExperienceStore`：介入中心每次审批/驳回（`interventions.py` 的 `decide_intervention`）自动调用 `experience.record_feedback(...)`，把 `{agent, action_type, decision(approved/rejected), context, note}` 沉淀为经验。
- 落 SQLite（`feedback_records` 表，按 `agent` 索引，租户隔离）+ 启动 `hydrate()` 回灌 → 偏好/禁忌记忆跨重启累积。
- 查询：`experience.agent_feedback_summary(agent)`（采纳/驳回/近 24h 驳回计数）、`get_preferences(agent)`、`get_forbidden(agent)`；API `GET /experience/{agent}`。

### 4.2 带护栏的自动调参（规则自学习）

- `strategy_tuner.auto_tune(tenant)`：复用 `suggest()` 效果规则，对命中的高置信方向**自动应用**旋钮，且受三重护栏：
  1. **总开关** `auto_tune_enabled`（默认开，env `ZHIYAN_AUTO_TUNE=0` 关）；
  2. **单次上限** `MAX_AUTO_PER_RUN=3`（一次最多自动调 3 个 Agent，防失控）；
  3. **冷却期** `AUTO_COOLDOWN_HOURS=24`（同一 Agent 24h 内不重复自动调，防抖动）。
- **一键回滚**：每次自动调参前拍快照，`rollback_last_auto()` 还原到调整前（`basis="auto_rollback"`，保留审计）。
- 反馈反哺：规则 2（收紧）新增「经验库近期驳回」信号——即使介入队列无驳回，只要该 Agent 近期被人类否定，也会建议收紧。

### 4.3 新增 API

| 端点 | 作用 |
|------|------|
| `POST /strategy/auto-tune/run` | 触发一次带护栏自动调参 |
| `POST /strategy/auto-tune/rollback` | 一键回滚最近一次自动调参 |
| `GET /strategy/auto-tune/status` | 护栏状态（开关/冷却/待回滚数） |
| `POST /strategy/auto-tune/set` | 开关自动调参 |
| `GET /experience/{agent}` | 查询某 Agent 的偏好/禁忌经验 |

## 5. P2 — 真·自进化（2026-07-25 已落地，v20.4）

把"记忆闭环(P0) + 规则自学习(P1)"再向前推一步：平台能**基于失败案例自我修订 prompt、把验证过的事实写入知识库、并从人类纠正中产出偏好信号**——且所有"变更类"动作都设**人工审批门**，绝不自动应用（安全铁律），只调整指令/约束/阈值，绝不改写业务数字（事实锚点）。

### 5.1 Prompt 自反思 + 版本化 + 人工审批门

- `src/runtime/evolution/reflection.py` 的 `LLMReflectionService.reflect(...)`：把某 Agent 近期被人类驳回的案例（`failure_store.collect_failure_cases` 从经验库派生）喂给 LLM，产出修订后的完整 `system prompt` + 变更理由；**LLM 不可用（无 Key / 调用失败）回退启发式**——在原文后追加「失败模式警示」附录。
- `src/runtime/evolution/prompt_versions.py` 的 `PromptVersionStore`：候选 prompt 进 `prompt_versions` 表（每 Agent 版本号自增），状态机 `proposed → approved → active`；**proposed 绝不自动应用**，必须人工 `approve` 再 `apply`。
- `apply` **热替换** live Agent 单例的 `system_prompt` 属性，并记录上一版内容；`rollback` 一键还原。租户隔离、启动 `hydrate()` 回灌，跨重启累积。

### 5.2 RAG 知识自更新

- `src/runtime/evolution/kg_facts.py` 的 `KgFactStore`：事实提议（`subject - predicate - object`，`draft`）经人工 `approve` 后 upsert 进 Neo4j 知识图谱（Entity 节点 + 关系边 + Insight），提升后续 RAG 召回质量。
- 事实锚点铁律：仅写实体/关系，绝不改写业务数字；Neo4j 不可达走内存图，不抛异常。

### 5.3 在线偏好学习 lite

- `src/runtime/evolution/preference_learning.py` 的 `preference_calibration(agent)`：基于经验库滚动批准率，产出信任度信号（trusted / needs_review / balanced）+ 被驳回最多的动作类型。该信号**仅供驱动其它模块**（如触发 Prompt 复盘、辅助策略自学习放宽阈值），绝不直接改业务数字。

### 5.4 新增 API

| 端点 | 作用 |
|------|------|
| `POST /evolution/reflect` | 复盘失败案例 → 生成候选 prompt（LLM/启发式）→ proposed |
| `GET /evolution/failure-cases/{agent}` | 查看该 Agent 的失败案例 |
| `GET /evolution/prompt-versions/{agent}` | 列出 Prompt 版本 + 当前 active |
| `POST /evolution/prompt-versions/{id}/approve` | 审批通过候选 prompt |
| `POST /evolution/prompt-versions/{id}/apply` | 应用（热替换 live 单例） |
| `POST /evolution/prompt-versions/{agent}/rollback` | 一键回滚 |
| `POST /evolution/kg-facts/propose` | 提议知识图谱事实 |
| `GET /evolution/kg-facts` | 列出事实提议 |
| `POST /evolution/kg-facts/{id}/approve` | 审批 → upsert 图谱 |
| `GET /evolution/preference/{agent}` | 在线偏好校准信号 |

---

**验证**：
- 记忆闭环：`pytest tests/test_memory_p0.py -v` + `python scripts/verify_memory_p0.py`
- 自学习闭环：`pytest tests/test_p1_self_learning.py -v` + `python scripts/verify_p1_self_learning.py`
- 自进化：`pytest tests/test_p2_evolution.py -v` + `python scripts/verify_p2_evolution.py`
（verify 脚本用 ASGITransport 直打 app，无需先启动 runtime）
