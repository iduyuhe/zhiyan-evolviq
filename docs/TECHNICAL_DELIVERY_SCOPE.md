# 技术落地范围基线与节奏控制

> 来源：思想落地已闭合（白皮书 v3 + 三图 HTML + 开放系统世界观共识，2026-08-03 杜总确认）。
> 授权：杜总 2026-08-03 指令——"沟通基本完成，按科学工程方法有序落实，控制节奏与范围，避免无限蔓延。"
> 本文是技术落地阶段的**范围基线（Scope Baseline）**，任何迭代不得越过本文边界，除非经杜总重新拍板。

---

## 1. 总体目标

把框架 **一脊·一体·四体系·一底座·五环节闭环** 从思想落地推进到技术落地，使系统在运行时真正跑通：
感知 → 认知（记忆 / 知识图谱 / 技能）→ 决策 → 执行（手 / 脚 + 人机协同闸门）→ 自我进化。

思想层已论证清楚，技术层只做"把已有思想翻译成可运行骨架"，不做新发明、不堆功能。

---

## 2. 在范围内（四刀，串行推进）

| 刀 | 名称 | 内核 | 落地形态 |
|---|---|---|---|
| 刀1 | 知识图谱升级 | 四级实体-关系图 | taxonomy 常量 + 从现有 case/预设抽取最小图谱 + 检索接口 |
| 刀2 | 行动层统一执行总线 | 手 / 脚 组织化 | 工具注册表 + 人机协同闸门（confirm/authorize/rollback/receipt） |
| 刀3 | 决策引擎 + 决策事件 | 认知→执行枢纽 | 决策建议生成 + 决策事件记录（证据可追溯） |
| 刀4 | 自我进化闭环 | 评估信号→资产更新 | 执行结果评估 → 记忆/图谱/技能/阈值资产回灌 |

**串行纪律**：完成一刀且验证通过（单测绿 + 不破坏既有 606 测试 + 对外零真名）后，再开下一刀。

---

## 3. 蔓延护栏（明确拒绝，违反即回退）

- ❌ **不扩行业**：维持 `telecom` / `semiconductor` / `consumer_electronics` / `new_energy` 4 类，不开光伏 / 工程机械 / 新能源汽车细化等。
- ❌ **不扩案例锚定**：维持每行业 10 上限（半导体已 10，其余维持现状 1）。超配额必须先替换、不得叠加。
- ❌ **不新增 Agent**：维持 25 个，不在技术落地阶段加新 Agent。
- ❌ **不新增 REST 端点**：除非闸门 / 检索必需且无替代；优先复用现有 `/api/cases/*`。
- ❌ **不新增前端组件**：复用现有面板（CaseLibraryPanel 等）；角标类微调允许，新建页面禁止。
- ❌ **不做图库重型迁移**：优先 UNS 关系表 / 内存图，降级兼容既有 SQLite；不引入 Neo4j 集群等重设施。
- ❌ **不碰模型参数**：进化发生在资产层（宝库 / 案例 / 预设 / 阈值），绝不微调 LLM 权重。

---

## 4. 节奏原则（每刀切 2–3 个最小迭代）

- 每迭代可独立验证：有单测、零真名泄漏、不破坏既有功能。
- 每迭代只改 1–2 个文件（遵循"零扩展挖存量"范式），改写单文件 ≤ 1。
- 双入口部署仅在该刀**对外可见**时触发（刀1 前几迭代纯后端结构化，可延迟部署，仅跑单测）。
- 每完成一刀，写一笔 `2026-08-03.md` 工作日志 + 必要时更新 MEMORY.md。

---

## 5. 各刀完成定义（DoD）

**刀1 知识图谱**
- 迭代1：taxonomy 常量（四级脊 + 实体 / 关系类型）+ 从 cases 抽取最小实体-关系（行业 / 产业节点 / 企业锚 × 竞争对标 / 价值链）+ 单测。✅ 本基线随附启动。
- 迭代2：价值链拓扑 + 竞品 / 供应关系（开放获取补全半导体 5 节点）。
- 迭代3：检索接口（按行业 / 节点 / 对标查询）+ 与孪生 / 记忆 / 技能绑定钩子。

**刀2 行动层**：工具注册表覆盖现有回写 / UNS / 文档 / API / 浏览器；人机协同闸门 confirm/authorize/rollback/receipt 标准接口；不可逆动作（ERP/MES 回写）先行上闸。

**刀3 决策引擎**：决策建议结构（候选动作 + 多目标权衡 + 约束校验 + 证据链）；决策事件持久化；北极星"决策实时化率"埋点。

**刀4 自我进化**：评估信号采集（执行结果 + 人工反馈）；资产更新通道（记忆 / 图谱 / 技能 / 阈值）；L0→L3 阶梯可观测。

---

## 6. 全程不可破的铁律

- 匿名铁律：对外字段零真名（`LEAK_TOKENS` 断言，与 compliance_reviewer 一致）。
- 凭证铁律：密钥加密 vault + 租户隔离，绝不明文落库 / 日志 / 外发。
- 审计三合一：匿名降 viewer + 租户上下文单一真相源 + 写回 pending 落盘可恢复。
- 配额铁律：每行业 国际5 + 国内5 = 10。
- 开放系统世界观：宝库 / 预设库 = 开放获取的加速层（非封闭库存）；外部清晰、内部抉择。

---

## 7. 当前进度

- 基线文档：✅ 已建（本文）。
- 刀1 迭代1：✅ 完成（taxonomy 常量 + builder 最小抽取 + 4 单测全绿；半导体 5 价值链节点归一化后生成对标边；对外零真名；**未部署，纯后端结构化，符合基线延迟部署纪律**）。
- 刀1 迭代2：✅ 完成（taxonomy 加 `VALUE_CHAIN_TOPOLOGY` 半导体 5 节点上下游拓扑常量；builder 据拓扑生成 `SUPPLIES` 供应边，连接上下游企业锚；新增 `test_kg_supplies_topology` 断言拓扑方向/零真名/不臆造未授权行业；共 5 测全绿；纯后端未部署）。
- 刀1 迭代3：✅ 完成（新 `src/knowledge_graph/retrieval.py`：`get_graph()` 懒加载工厂 + `get_enterprises_by_node/get_competitors/get_upstream/get_downstream` 匿名检索视图 + `resolve_binding_target` 绑定钩子骨架；KGGraph 加 enterprises_by_node/competitors_of/upstream_of/downstream_of 方法；`tests/test_kg_iter3.py` 7 测全绿；对外零真名；纯后端未部署）。
- **刀1 知识图谱升级：✅ 全刀完成（迭代1/2/3 单测全绿 + 全量 618 测试 0 回归，符合串行纪律）**。
- 刀2 行动层统一执行总线：✅ 完成（迭代1 = `src/runtime/action_bus.py` ActionBus wrapper 复用 TOOL_REGISTRY + ActionSpec + 闸门接口 confirm/authorize/rollback/receipt + 不可逆动作 `require_gate` 分类；迭代2 = 闸门接 `writeback.py` 审计三合一（pending 落盘可恢复），execute 即留审计 pending、rollback 取消未过账记录；`tests/test_action_bus.py` 9 测全绿；纯后端未部署）。
- 刀3 决策引擎 + 决策事件：✅ 完成（新 `src/runtime/decision.py`：DecisionProposal 结构=候选动作+多目标权衡(成本/交期/风险/质量/合规)+约束校验(治理前置，不通过抑制推荐)+证据链(case_id/kg_node 零真名)；DecisionStore 决策事件持久化(SQLite 复用 writeback 同源韧性降级)+`north_star()` 北极星=决策实时化率 executed/total(MVP 0.40/稳态 0.85，不 round 保全精度)；`build_proposal` 约束前置抑制；`tests/test_decision.py` 8 测全绿；**全量 635 测 0 回归**；纯后端未部署）。
- 刀4 自我进化闭环：
  - 迭代1（评估信号采集）：✅ 完成（新 `src/runtime/evolution_loop.py`：EvaluationSignal 归一信号 dataclass + EvolutionLoop.collect 从 consequence(蓝弧) + feedback_store(共生环) 挖存量采集、去重、SQLite 持久化(韧性降级纯内存)、stats 分源统计；路由规则 validated→阈值/contradicted→技能/关联事实→图谱、like→记忆/dislike→阈值/idea→技能；零真名：执行信号不携业务数字、反馈信号含 LEAK_TOKENS 残留一律丢弃；`feedback_store.py` 加 `list_all()` 只读方法（1 处小改）；`tests/test_evolution_iter1.py` 8 测全绿；纯后端未部署）。
  - 迭代2（资产更新通道 + L0→L3 阶梯）：✅ 完成（evolution_loop.py 加 `AssetUpdateIntent` + `apply_signals`（信号→四类资产通道：记忆→experience.record_feedback 真实回灌 / 图谱→记录置信调整提议 / 技能→复盘候选 / 阈值→strategy_tuner.suggest 仅提议，绝不自动应用，status 全 proposed）+ `_make_intent` 幂等 + `evolution_ladder()` L0→L3 可观测（L1 已采集/L2 已产意图/L3 跨≥2 agent 复利）；SQLite 持久化(韧性降级纯内存)；`tests/test_evolution_iter2.py` 7 测全绿；纯后端未部署）。
  - **刀4 自我进化闭环：✅ 全刀完成（迭代1/2 单测全绿 + 挖存量 consequence/feedback_store/experience/strategy_tuner，零真名，符合串行纪律）**。

## 8. 对外可见阶段（2026-08-03 杜总指令：双入口部署 / 前端角标 / 案例库扩锚定）

- 触发条件：四刀技术落地全刀完成（650 测 0 回归），进入「对外可见」——延迟部署纪律解除，核心+边缘双入口上线。
- 案例库扩锚定（适度补缺）：✅ 完成。通讯/3C/新能源 各补到 5（国际3+国内2），共 +12；半导体不动（10 满额）。每行业配额=国际≤5+国内≤5=≤10（铁律）。新锚 case_id 全部**匿名化**（无公司名片段，规避 LEAK_TOKENS 命中）；对外字段(subject_anon/derived_insights/disclosure_facts)零真名；real_anchor 仅 internal 视图。案例库总量=25（半导体10+通讯5+3C5+新能源5）。
- 前端常驻角标：✅ 完成。`studio/src/App.tsx` 右下角常驻「智衍 · 决策孪生 v{版本}」（非交互、不挡 UI）；版本经 vite `define __APP_VERSION__`（Docker build-arg GIT_SHA / 本地 git HEAD）注水印 = `2f0c5cc`。
- 双入口部署：✅ 完成。
  - 核心 `http://43.153.172.52:3006`：`_push_sync.py --deploy`（bundle→SCP→服务器 reset→build runtime+studio→up），GitHub 同步 OK。
  - 边缘 `https://zhiyan.weomnitech.com.cn`：`edge_sync_release.py`（本地 `vite build` → 上传 dist → 切软链，失败自动回滚），校验骨架屏+版本水印+/api/health=200 通过。
  - 双端 `smoke_check.py` 均 PASS（前端不会白屏，三层防御生效）。
  - 活体校验：/cases/library 返回 25 个锚（12 新锚全在），逐案例 payload 扫描 LEAK_TOKENS + `real_anchor` = **零命中**。
- 全量回归：✅ `pytest` 652 passed（1 条 asyncio teardown 警告，非失败）。
- 纪律校验：✅ 白屏三层防御、鉴权三铁律、配额铁律、零真名铁律、vite 先 commit 再 build、部署后 smoke_check 全部遵守。
