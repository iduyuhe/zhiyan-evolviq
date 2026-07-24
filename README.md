# 智衍 EvolvIQ · AI 原生工业智能体平台

> 智衍（EvolvIQ）是一个面向电子制造 / 半导体行业的 **AI 原生工业智能体开发与部署平台**：把供应链、设备维护、良率、质量、DFM、BOM 选型、OEE、ECO、换线、AOI、IPC 标准、计划排程、能源碳 ESG、制造成本等 20 类工业场景，封装为可直接调用的自治 Agent，并通过统一网关接入 Modbus / MQTT / OPC-UA / IPC-CFX 等工业协议，配合跨 Agent 知识图谱与按效果调参的授权引擎，实现「感知—规划—执行—复盘」闭环。

## ✨ 核心特性

- **20 个工业 Agent**：覆盖研发、供应链、制造、质量、经营决策全链路（见下表）
- **4 类工业协议网关**：Modbus / MQTT / OPC-UA / IPC-CFX，真实数据源或模拟模式自动切换
- **MCP 能力联邦**：65 个标准化工具，HTTP + stdio 双传输
- **跨 Agent 知识图谱**：基于 Neo4j 的可追溯知识网络（缺 Neo4j 时自动回退内存图）
- **按效果调参的授权引擎**：置信度阈值、每日自主上限、人类介入队列
- **韧性降级**：PostgreSQL / Neo4j / 各网关不可达时自动回退 SQLite / 内存图 / 模拟模式，绝不阻断启动
- **多租户隔离**：行级 `tenant_id` 隔离 + API Key 认证（`X-Tenant-Key`），开放自助注册，未带密钥自动归属默认租户 `default`，向后兼容

## 🧩 20 个 Agent 一览

| Agent | 场景 | 核心能力 |
|------|------|------|
| `supply_chain` 供应链 | 物料齐套 / 缺料预警 / 替代推荐 | 齐套检查、缺料预警、国产替代评估 |
| `pm_maintenance` 设备维护 | 设备健康诊断 / 预测维护 | 健康评分、备件更换预警 |
| `yield_analysis` 良率分析 | 晶圆良率 / 缺陷定位 | 良率趋势、缺陷分类、根因定位 |
| `quality_trace` 质量追溯 | 客诉→批次→工艺→设备 | 端到端溯源、纠正措施 |
| `dfm_check` DFM 检查 | PCB/PCBA 可制造性 | 焊盘间距 / 线宽 / 阻焊规则校验 |
| `bom_selector` BOM 选型 | 元器件智能选型 | pin-to-pin 替代、EOL 预警 |
| `oee_optimizer` OEE 优化 | 产线综合效率 | 六大损失分析、瓶颈识别 |
| `eco_change` ECO 变更 | 工程变更影响 | 受影响 BOM / WIP / 库存识别 |
| `smt_changeover` 换线 | SMT 换线优化 | SMED、料站预配 |
| `aoi_judge` AOI 判定 | AOI 误报过滤 | 误报根因、阈值优化 |
| `ipc_standard` IPC 标准 | IPC 标准判定 | Class 1/2/3 分级、检验方法 |
| `aps_scheduler` 计划排程 | 生产排程 / 产能负荷 / 交期 | 产能负荷、瓶颈识别、交期承诺(CTP) |
| `energy_carbon` 能源碳ESG | 能耗 / 碳排放 / 节能降碳 | 碳核算、绿电比例、ESG 合规 |
| `cost_analysis` 制造成本 | 单位成本拆解 / 降本 / 报价 | 成本拆解、降本机会、毛利率 |
| `demand_order` 需求订单 | 需求预测 / 订单履约 / 产销协同 | 需求-产能对齐、交期风险、S&OP 再平衡 |
| `wms_logistics` 仓储物流 | 库存健康 / 物流时效 / 自动补货 | 安全库存预警、周转与呆滞、在途监控 |
| `compliance_q` 质量合规 | 认证体系 / 审核发现 / 法规合规 | ISO 认证跟踪、CAPA、RoHS/REACH |
| `executive_cockpit` 经营驾驶舱 | 经营KPI / 预算 / 产出追踪 | 营收/毛利、预算执行、产出完成率 |
| `rd_npi` 研发新产导入 | NPI 项目 / 里程碑 / 试产 | 项目阶段、里程碑跟踪、风险识别 |
| `procurement_manage` 采购供应商 | 供应商绩效 / 合同 / 策略 | 四维评分、合同管理、供应商评审 |

## 🚀 快速开始

### 方式一：本地 Python（最简，自动降级）

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # 至少填入你的 LLM_API_KEY
python -m src.runtime.main
# 打开 http://localhost:8000/docs
```

无需 PostgreSQL / Neo4j，平台会以 **SQLite + 内存图 + 模拟网关** 运行；`ZHIYAN_DEMO_DATA=1` 会注入演示数据。

### 方式二：Docker 一键起（含 PG + Neo4j + 前端）

```bash
cp .env.example .env        # 至少填入 LLM_API_KEY
docker compose up -d
# 前端：http://localhost:8080    后端 API：http://localhost:8000
```

网关（Modbus/MQTT/OPC-UA/IPC-CFX）在数据源不可达时自动以 `simulated` 模式运行。

## 🔧 环境变量（详见 `.env.example`）

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` / `LLM_BASE_URL` | 主 LLM 通道（OpenAI 兼容） |
| `HUNYUAN_API_KEY` / `HUNYUAN_BASE_URL` | 备用通道（腾讯混元，可选） |
| `ZHIYAN_DB_URL` | PostgreSQL 连接串；留空自动用 SQLite |
| `NEO4J_URI` / `NEO4J_PASSWORD` | Neo4j；留空自动回退内存图 |
| `ZHIYAN_DEMO_DATA` | `1` = 启动时注入演示数据 |
| `TENANT_ADMIN_KEY` | 平台管理员密钥；配置后 `GET /tenants` 等管理接口生效（见下方多租户模式） |

## 🏢 多租户模式

智衍内置完整多租户能力：多个租户共享同一套部署，数据按 `tenant_id` 行级隔离，彼此不可见。**未携带租户密钥的请求自动归属默认租户 `default`**，因此现有匿名调用与集成测试行为完全不变（向后兼容）。

### 隔离范围

- 会话（`AgentSession`）、审计日志（`AuditLog`）、授权边界（`AuthorizationBoundary`）按租户隔离
- 跨 Agent 知识图谱的节点 / 边带 `tenant` 标签，查询按租户过滤
- 工业协议网关可按租户覆写连接参数；未配置则共享平台网关
- MCP 能力联邦、按效果调参的授权引擎均按租户隔离

### 认证方式

需要隔离的接口通过请求头 `X-Tenant-Key: <api_key>` 识别租户。平台密钥仅存储哈希，明文 `api_key` 仅在**注册 / 轮换时一次性返回**，请妥善保存。无效或已失效的密钥返回 `401`。

### 快速使用

**1. 注册租户**（开放自助，返回明文 `api_key`）

```bash
curl -X POST http://localhost:8000/tenants/register \
  -H "Content-Type: application/json" \
  -d '{"name": "acme"}'
# → {"tenant_id":"t_xxx","name":"acme","api_key":"<明文 key，仅此一次可见>","note":"..."}
```

**2. 携带密钥调用平台接口**（会话 / 边界 / 审计 / 知识图谱 / 网关 / MCP 全部按租户隔离）

```bash
curl http://localhost:8000/sessions -H "X-Tenant-Key: <你的 api_key>"
```

**3. 查询 / 轮换 / 注销当前租户**

```bash
curl http://localhost:8000/tenants/me              -H "X-Tenant-Key: <key>"
curl -X POST http://localhost:8000/tenants/rotate  -H "X-Tenant-Key: <key>"
curl -X DELETE http://localhost:8000/tenants/me    -H "X-Tenant-Key: <key>"
```

**4. 为租户配置独立工业网关**（可选，缺省字段沿用平台共享网关）

```bash
curl -X PUT http://localhost:8000/tenants/gateway-config \
  -H "X-Tenant-Key: <key>" -H "Content-Type: application/json" \
  -d '{"modbus_host":"10.0.0.5","mqtt_broker":"broker.acme.com"}'
```

**5. 平台管理**（需配置 `TENANT_ADMIN_KEY` 环境变量，并以请求头 `X-Platform-Admin-Key` 调用）

```bash
curl http://localhost:8000/tenants -H "X-Platform-Admin-Key: <admin_key>"
```

### 租户管理接口一览

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/tenants/register` | 自助注册，返回明文 `api_key` | 开放 |
| GET | `/tenants/me` | 当前租户信息 | `X-Tenant-Key` |
| POST | `/tenants/rotate` | 轮换密钥，返回新明文 key（旧 key 立即失效） | `X-Tenant-Key` |
| DELETE | `/tenants/me` | 注销当前租户（默认租户不可删） | `X-Tenant-Key` |
| GET | `/tenants` | 列出全部租户 | `X-Platform-Admin-Key` |
| PUT | `/tenants/gateway-config` | 设置租户网关连接参数覆写 | `X-Tenant-Key` |
| GET | `/tenants/gateway-config` | 读取租户网关配置（`null` = 共享平台网关） | `X-Tenant-Key` |

完整接口定义与字段见 `http://localhost:8000/docs`（Swagger UI）。

## 📂 目录结构

- `src/` 后端（FastAPI 运行时 + 20 个 Agent + 网关 + 知识图谱 + 授权引擎）
- `studio/` 前端（React + Vite + Tailwind）
- `infra/` Dockerfile 与网关模拟器
- `scripts/` 种子 / 压测 / 验证脚本
- `docs/` 战略对齐与评估报告

## 📜 开源协议

[Apache License 2.0](LICENSE)。详见 [`NOTICE`](NOTICE)。

## 🤝 贡献

欢迎 Issue / PR。提交即表示同意以 Apache-2.0 协议贡献。
