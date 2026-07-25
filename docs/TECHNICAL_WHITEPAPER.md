# 智衍 EvolvIQ 技术白皮书

> **AI 原生工业智能体平台 · 架构设计与实现**
> 版本 v20 · 20 工业 Agent · 65 MCP 工具 · 4 类工业协议网关
> 文档日期：2026-07-25 · 面向架构师 / 集成商 / AI 工程师 / 开源贡献者

---

## 文档信息

| 项 | 内容 |
|----|------|
| 平台 | 智衍 EvolvIQ（Zhiyan EvolvIQ） |
| 版本 | v20 |
| 后端技术栈 | FastAPI (Python 3.13) · Neo4j · PostgreSQL / SQLite · Docker |
| 前端技术栈 | React + Vite + Tailwind (Node 22) |
| 许可证 | Apache-2.0 |
| 仓库 | `github.com/iduyuhe/zhiyan-evolviq` |
| 生产实例 | `http://43.153.172.52:3006` |

---

## 执行摘要（技术视角）

智衍 EvolvIQ 在技术上解决一个核心问题：**如何让 20 个异构工业能力以一个统一、可审计、可降级、可自治的方式被调用与执行**。

技术选型的关键决策：

1. **统一契约而非统一实现**：`BaseAgent.analyze(goal) -> dict` 是唯一的接入契约，各 Agent 内部算法自由，但对外行为一致。
2. **惰性加载与韧性降级**：所有重依赖（数据库 / 图库 / 网关客户端）都延迟 `import`、失败时回退本地替代，系统永不因单点故障宕机。
3. **规则路由而非 LLM 路由**：`ROUTING_RULES` 关键词顺序匹配，确定性、可测试、零延迟，避免「用大模型选 Agent」的不可控与高成本。
4. **授权内自治**：每个 Agent 有独立 `AuthBoundary`，量化约束（置信度 / 日限额 / 价格容忍）实时生效，越界动作进人工队列。
5. **网关机会性升级**：网关初连失败进入 `simulated` 模式，后台周期性重试真实连接，成功自动切 `live`——演示与生产无缝过渡。

---

## 第一章 技术架构总览

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────────┐
│ 前端 (studio)  React+Vite+Tailwind  :3006 nginx 反代 /api   │
├──────────────────────────────────────────────────────────┤
│ 治理层   授权引擎 · 多租户 · 审计日志 · 按效果调参           │
├──────────────────────────────────────────────────────────┤
│ 智能层   AgentEngine(plan/execute) · 20 Agent · 知识图谱     │
├──────────────────────────────────────────────────────────┤
│ 能力层   MCP 联邦(65 工具) · 路由引擎 · 授权评估             │
├──────────────────────────────────────────────────────────┤
│ 接入层   网关管理器(OPC-UA/MQTT/Modbus/IPC-CFX) · persistence │
└──────────────────────────────────────────────────────────┘
```

### 1.2 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| Web 框架 | FastAPI (async) | 原生 `async` 支持高并发 Agent 调用 |
| 运行时 | Python 3.13-slim | Docker 镜像基础 |
| 图数据库 | Neo4j（可选） | 不可用时回退内存邻接表 |
| 关系库 | PostgreSQL / SQLite | 按 `ZHIYAN_DB_URL` 自动切换 |
| 消息/网关 | RabbitMQ·Mosquitto·OPC-UA Server | 对应四类网关，均带模拟器 |
| 前端 | React 22 + Vite + Tailwind | SPA，nginx 容器内反代 |
| 包管理 | pyproject + venv / npm | 开发态依赖隔离 |

### 1.3 进程模型

- `runtime` 容器：FastAPI（`uvicorn`），监听 8000，对外经 studio nginx 的 `:3006/api` 暴露。
- `studio` 容器：React 静态站 + nginx，`/api` 反向代理到 `runtime:8000`。
- 其余容器：postgres / neo4j / mosquitto / modbus-sim / opcua-server / rabbitmq / mqtt-publisher / ipc-cfx-publisher——均为可选，缺失即降级。

---

## 第二章 核心抽象：Agent 契约

### 2.1 统一契约 `BaseAgent`

所有 Agent 遵循最小契约（源码 `src/agents/base.py`）：

```python
class BaseAgent(ABC):
    name: str = "base"            # 路由注册键
    description: str = ""

    @abstractmethod
    async def analyze(self, goal: str) -> dict:
        """自然语言目标 → 结构化结果"""
        ...
```

- 入参 `goal`：自然语言目标文本。
- 返回 `dict`：至少含 `status` / `summary`，路由层补写 `result["agent"]`。
- `@abstractmethod` 保证漏实现在实例化时报错，而非运行时静默失败。

### 2.2 历史兼容适配

早期 Agent 入口方法名不统一（`supply_chain` 用 `analyze_goal()+execute()`，`quality_trace` 用 `trace()`）。现状策略：保留旧方法向后兼容，各自补 `analyze()` 适配器对外统一。贡献新 Agent 只需实现 `analyze()`。

### 2.3 双内核设计

每个 Agent 内部 = **确定性算法内核 + LLM 规划外壳**：

- 算法内核：齐套率、产能负荷、碳核算等真实计算，结果可复现。
- LLM 外壳：目标拆解、工具编排、结论组织。

这避免了「纯大模型套提示词」的不可控与幻觉，保证结论可审计。

---

## 第三章 路由引擎

### 3.1 注册表（惰性加载）

`src/runtime/agent/router.py` 的 `AGENT_REGISTRY` 是 `agent_name → (模块路径, 单例名)` 的映射。通过 `importlib.import_module` 在 `get_agent()` 时按需加载，**未被调用的 Agent 不占内存、不触发依赖 import**。

```python
AGENT_REGISTRY = {
    "supply_chain": ("src.agents.supply_chain.agent", "supply_chain_agent"),
    "procurement_manage": ("src.agents.procurement_manage.agent", "procurement_agent"),
    # ... 共 20 项
}
```

### 3.2 顺序敏感路由（铁律）

`ROUTING_RULES` 是 `(关键词列表, agent_name)` 有序列表。`route_goal()` 顺序遍历，**首个命中即返回**——因此是顺序敏感而非优先级表。

**铁律**：新 Agent 关键词必须按语义紧密度插入正确位置，不能追加末尾。教训：

- `demand_order` 必须放在 `aps_scheduler` 之前（否则 aps 的「交期」截获「交期风险」）。
- `wms_logistics` 必须放在 `supply_chain` 之前且**不含裸词「库存」**（否则抢供应链物料查询）。
- `procurement_manage` 的「供应商」含 supply_chain 的「供应」子串，必须用复合词（供应商绩效/合同到期）并前置规则避免误截获。

### 3.3 路由算法

```python
def route_goal(goal: str) -> str:
    goal_lower = goal.lower()
    for keywords, agent_name in ROUTING_RULES:
        for kw in keywords:
            if kw.lower() in goal_lower:
                return agent_name
    return "supply_chain"   # 默认兜底
```

为什么不用 LLM 路由：确定性、零延迟、可断言测试（路由准确率可 100% 覆盖），且不受模型波动影响。

---

## 第四章 规划与执行引擎

### 4.1 生命周期

`AgentEngine`（`src/runtime/agent/engine.py`）管理会话全生命周期：

```
planning → ( human confirm ) → executing → completed
                                  ↓
                            intervene (人工介入队列)
```

`plan()` 接收目标 → 路由选 Agent → 生成 Markdown 规划（展示给人确认）→ 落库 `AgentSession` 并写审计日志 → `execute()` 调用 `BaseAgent.analyze()` 执行。

### 4.2 通用规划元组

企业级 Agent（aps / energy / cost / demand / wms / compliance / executive / rd / procurement）走通用规划路径，由 `engine.plan()` 内 10 元组分发，避免每 Agent 写一套模板。

### 4.3 `lines` 键 schema 感知（关键修复）

`result['lines']` 被 OEE（产线效率 schema）与 energy_carbon（能耗 schema）两类 Agent 复用，初始引擎一律按 OEE 解析 → `KeyError: line_name` → HTTP 500。

**修复**：`_plan_for_generic_agent` 按 schema 区分分支——含 `oee` 走 OEE 渲染，含 `energy_kwh` 走能耗渲染，其它跳过。新增 Agent 若复用 `lines` 键必须同步改此处，否则必崩。

---

## 第五章 授权引擎

### 5.1 边界模型 `AuthBoundary`

每个 Agent 一个默认边界（源码 `src/runtime/core/authorization.py` 的 `_build_default_boundaries()` 构造 20 个）：

| 字段 | 含义 |
|------|------|
| `confidence_threshold` | 低于此置信度动作需审批 |
| `max_daily_autonomous` | 每日自主执行上限 |
| `auto_execute_actions` | 授权内可直接执行的动作 |
| `require_approval_actions` | 必须人工审批的动作 |
| `allowed_categories` | 物料 / 设备类目白名单 |
| `price_tolerance_pct` | 价格容忍幅度 |

### 5.2 评估流程

```
动作 → 在 require_approval_actions? → 是: 进人工队列
                        ↓ 否
      量化约束越界(置信度/日限额/价格/数量)? → 是: 进人工队列
                        ↓ 否
                  授权内自主执行 (auto_executed)
```

实测中 `demand_order` 的 S&OP 再平衡即在此路径下自主执行。

### 5.3 多租户作用域

全局单例 `authorization` 提供 `for_tenant(tid)` 返回 `TenantAuthScope` 视图，所有 CRUD/评估限定该租户。`default` 租户为兼容默认。

### 5.4 按效果调参（StrategyTuner）

`StrategyTuner` 只调阈值（夹紧 `confidence ∈ [0.5, 0.95]`），不碰业务数字——事实锚点铁律。调参经 `authorization.patch()` 直接改内存单例，**实时生效**，下次动作评估即应用新阈值。

---

## 第六章 韧性降级工程

这是平台最关键的工程决策——**任何外部依赖不可达，系统自动回退本地替代，绝不阻断启动或执行管道**。

### 6.1 延迟 import 模式

重客户端库（neo4j / asyncua / pymodbus / paho / aio_pika）全部**延迟 import**：放在 `connect()` 内部而非模块顶层。沙箱缺失这些库时，模块导入不报错，仅 `connect()` 时回退。

### 6.2 数据库 PG → SQLite

`ZHIYAN_DB_URL` 留空 → 自动用 SQLite 文件；填入 → 用 PostgreSQL。切换对业务代码透明（`persistence` 层抽象）。

### 6.3 知识图谱 Neo4j → 内存

`NEO4J_URI` 留空 → 内存邻接表；填入 → Neo4j。图谱分析降级但核心可用。

### 6.4 网关 simulated + 机会性重试

`src/gateways/manager.py` 实现网关连接管理：

```python
# manager.py:57-89
# 启动机会性升级循环：网关处于 simulated 时，周期性重试真实连接，
# 成功则自动切 live。上限 attempts*interval 秒后保持 simulated。
if getattr(gw, "_mode", "simulated") == "simulated":
    # 后台重试真实连接
    ...
```

首次 `connect` 可能因依赖服务未就绪而回退 `simulated`；后台周期重试，就绪后无缝切 `live`。**演示永不中断**。

### 6.5 健康检查铁律

Docker 健康检查**禁用** `cat < /dev/null > /dev/tcp/...`（bashism，Debian/ alpine 不支持 → 全假 unhealthy → 依赖 `service_healthy` 的服务永不启动）。改用原生工具：`pg_isready` / `wget`（neo4j）/ `nc -z`（mqtt/modbus）/ `python3 -c socket`（opcua）/ `rabbitmq-diagnostics ping`。

---

## 第七章 数据接入层

### 7.1 四类网关接口格式（代码已验证）

| 网关 | 传输 / 端口 | 客户端库 | 读 / 写 |
|------|------------|---------|---------|
| OPC-UA | `opc.tcp://host:4840` | asyncua | 节点读 + 写（可控制） |
| MQTT | `broker:1883` | paho-mqtt | 订阅主题 + 发布下发 |
| Modbus | `host:port`（TCP 502） | pymodbus | coil / holding 读 + 写 |
| IPC-CFX | AMQP 1.0（RabbitMQ） | aio-pika | `CFX.*` 事件消费 |

所有网关：惰性 `import` + `connect()` 失败回退 `simulated` + 机会性重试升级 live。

### 7.2 MCP 联邦

`src/runtime/mcp/federation.py` 聚合 65 个标准化工具，命名空间 `agent__method`（如 `supply_chain__check_shortage`）。对外经 **HTTP `/mcp/tools` 或 stdio** 双传输暴露，可被上层 Agent 或外部系统调用——即「能力货架」。

### 7.3 业务数据层

- 种子数据：`data/seed/` 17 个 JSON 文件，开箱即用（半导体风格）。
- 持久化：PostgreSQL / SQLite（`ZHIYAN_DB_URL`）。
- 真实 MES/ERP：改写各 Agent 的 `tools.py` 数据源接口，工作量约 1–2 周/源。

---

## 第八章 跨 Agent 知识图谱

- **存储**：Neo4j（优先）/ 内存邻接表（回退）。
- **写入**：`engine` 在动作执行后 `fire-and-forget` 增量写入「决策—依据—结果」边，不阻塞主流程。
- **租户**：节点 / 边带 `tenant` 标签，查询按租户过滤。
- **价值**：每次 Agent 输出可溯源、可复盘，支撑持续改进与合规审计。

---

## 第九章 多租户与隔离

- **隔离粒度**：`tenant_id` 行级隔离，覆盖会话 / 审计 / 边界 / 图谱节点。
- **认证**：请求头 `X-Tenant-Key: <api_key>`；无效 / 失效返回 401。
- **默认租户**：未带密钥自动归属 `default`，向后兼容既有调用。
- **租户网关覆写**：`PUT /tenants/gateway-config` 可为租户独立配置 Modbus/MQTT 等连接参数。
- **管理**：配置 `TENANT_ADMIN_KEY` 后，`X-Platform-Admin-Key` 可列全部租户。

---

## 第十章 API 设计

### 10.1 端点清单（部分）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/quick-check` | 自然语言目标 → 路由 + 执行 + 返回结果 |
| GET | `/api/agents` | 20 Agent 元数据 |
| GET | `/api/health` | 健康检查 |
| GET/POST | `/tenants/*` | 租户注册 / 查询 / 网关覆写 |
| GET | `/kg/*` | 知识图谱查询 |
| GET | `/strategy/*` | 面板 / 建议 / 调参 / 审计 |

> 注意：路由无 `/api` 前缀（该前缀由 studio nginx 加）；本地直连 runtime 用 `:8000/api/...`。

### 10.2 quick-check 流程

```
POST goal → route_goal() 选 Agent → AgentEngine.plan()
         → BaseAgent.analyze() 执行 → 授权评估 → 返回结构化结果
```

### 10.3 认证与审计

所有动作经 `audit_logger.log()` 写审计（含 `session_id` / `actor` / `tenant_id`），支持合规回溯。

---

## 第十一章 前端架构

- **技术**：React + Vite + Tailwind（Node 22），SPA + nginx 反代。
- **四接线点**（新增 Agent 必须同步改）：
  1. `AgentSelector.tsx` — `SCENARIO_GROUPS` 场景分组
  2. `App.tsx` — 分发列表
  3. `GenericResultView.tsx` — `AGENT_META` + `getTabs()` + 渲染函数
  4. `StrategyTuningTab.tsx` — 计数文案
- **渲染模式**：`AGENT_META` 描述元数据，`getTabs()` 返回标签页，各 Agent 有独立渲染函数——新增能力不破坏既有 UI。

---

## 第十二章 测试与质量保障

- **单元 / 集成**：`pytest` 全量 **51 passed / 0 failed**（约 20s），覆盖路由 / 引擎 / 授权 / 网关 / Agent 端到端。
- **路由断言**：`assert route_goal("交期风险预测") == "demand_order"` 类测试锁定顺序铁律，防止回归。
- **CI**：`.github/workflows/ci.yml` 自动跑 pytest + `tsc` + docker build（需 PAT `workflow` scope）。

---

## 第十三章 部署与运维

- **编排**：`docker-compose.prod.yml` 含 10 服务（runtime / studio / pg / neo4j / mosquitto / modbus-sim / opcua-server / rabbitmq / mqtt-publisher / ipc-cfx-publisher），含日志轮转 `x-logging`。
- **入口**：对外仅 `:3006`（studio），runtime 8000 仅在容器内。
- **最小栈**：`docker-compose.deploy.yml`（runtime + studio + 演示数据 + 韧性降级），快速起。
- **生产配置**：`ZHIYAN_DEMO_DATA=1` 注入演示数据；外部入口经 studio nginx 反代。

---

## 第十四章 扩展开发指南（新增一个 Agent）

后端四处接线 + 前端四处接线 + 文档：

1. `router.py`：`AGENT_REGISTRY` 加项 + `ROUTING_RULES` **按语义插入正确位置**
2. `engine.py`：通用规划元组扩（企业级）或加专用分支
3. `federation.py`：`import` + `_INSTANCES` + `TOOL_REGISTRY`
4. `authorization.py`：`_build_default_boundaries()` 加默认边界
5. `agents_api.py`：加元数据
6. 前端四接线点（见第十一章）
7. `README.md` 更新 Agent 计数与表格
8. **必须**写路由断言测试锁定命中

---

## 第十五章 已知技术债务与路线图

| 项 | 优先级 | 技术说明 |
|----|:------:|---------|
| 多 Agent 编排 / 协作 | P1 | 当前 20 Agent 各自为战，缺协同引擎（T4 收敛项） |
| 路由精度 | P1 | 语义相近 goal 存在歧义（如「生产排程产能负荷」误路由 demand_order） |
| 英文前端 i18n | P2 | 文档已国际化，前端待翻译工程 |
| `lines` 键复用 | P2 | 多 Agent 复用同一键，新增须同步改 engine 分支 |
| LLM 深度 | P2 | 规划层可接更强模型 / 多模型路由 |

---

## 附录 A：关键文件索引

| 文件 | 职责 |
|------|------|
| `src/agents/base.py` | `BaseAgent` 统一契约 |
| `src/runtime/agent/router.py` | `AGENT_REGISTRY` + `ROUTING_RULES` + `route_goal` |
| `src/runtime/agent/engine.py` | `AgentEngine` 规划/执行生命周期 |
| `src/runtime/core/authorization.py` | 授权引擎 + 20 默认边界 |
| `src/runtime/mcp/federation.py` | 65 MCP 工具联邦 |
| `src/gateways/manager.py` | 4 类网关连接管理 + 机会性重试 |
| `src/gateways/{opcua,modbus,mqtt,ipc_cfx}/` | 各网关实现 |
| `studio/src/components/{AgentSelector,GenericResultView,StrategyTuningTab}.tsx` | 前端四接线点 |
| `docker-compose.prod.yml` | 生产 10 服务编排 |

## 附录 B：术语

| 术语 | 说明 |
|------|------|
| `BaseAgent.analyze` | 所有 Agent 的统一调用契约 |
| `ROUTING_RULES` | 顺序敏感的关键词→Agent 路由表 |
| `AuthBoundary` | 单 Agent 的安全与自治约束集 |
| 韧性降级 | 依赖不可达时自动回退本地替代 |
| 机会性重试 | 网关 simulated 态后台重试真实连接并自动升级 |
| MCP 联邦 | 65 工具经 HTTP/stdio 对外暴露的能力货架 |
| 按效果调参 | StrategyTuner 实时夹紧置信度阈值 |

---

*本技术白皮书基于智衍 EvolvIQ v20 真实源码撰写，类名 / 文件名 / 行号均来自仓库当前状态。*
