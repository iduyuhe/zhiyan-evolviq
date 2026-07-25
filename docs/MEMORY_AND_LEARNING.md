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
| 规则自学习闭环 | 🟡 P1（待做） | strategy_tuner 从"建议"升级为"带护栏自动应用" |
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

## 4. P1 — 规则自学习闭环（建议下一步）

1. `strategy_tuner` 从「建议」升级为「带护栏的自动应用」：达标即微调旋钮，人可一键回滚。
2. 经验库：将人类「驳回 / 采纳」打标签，沉淀为 agent 的「偏好 / 禁忌」记忆，推理时由 `recall` 读回。

## 5. P2 — 真·自进化（远景）

1. **Prompt 自反思**：LLM 复盘失败案例 → 自动修订 agent `system prompt`（版本化 + 人工审批）。
2. **RAG 知识自更新**：把验证过的结论自动写入知识库，下次检索即用。
3. **在线学习信号**：人类纠正转为训练信号（偏好学习 / RLHF-lite）。

---

**验证**：`pytest tests/test_memory_p0.py -v` + `python scripts/verify_memory_p0.py`（需先启动 runtime）。
