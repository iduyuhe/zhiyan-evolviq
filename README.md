# 智衍 EvolvIQ · AI 原生工业智能体平台

> 智衍（EvolvIQ）是一个面向电子制造 / 半导体行业的 **AI 原生工业智能体开发与部署平台**：把供应链、设备维护、良率、质量、DFM、BOM 选型、OEE、ECO、换线、AOI、IPC 标准等 11 类工业场景，封装为可直接调用的自治 Agent，并通过统一网关接入 Modbus / MQTT / OPC-UA / IPC-CFX 等工业协议，配合跨 Agent 知识图谱与按效果调参的授权引擎，实现「感知—规划—执行—复盘」闭环。

## ✨ 核心特性

- **11 个工业 Agent**：覆盖研发、供应链、制造、质量全链路（见下表）
- **4 类工业协议网关**：Modbus / MQTT / OPC-UA / IPC-CFX，真实数据源或模拟模式自动切换
- **MCP 能力联邦**：38 个标准化工具，HTTP + stdio 双传输
- **跨 Agent 知识图谱**：基于 Neo4j 的可追溯知识网络（缺 Neo4j 时自动回退内存图）
- **按效果调参的授权引擎**：置信度阈值、每日自主上限、人类介入队列
- **韧性降级**：PostgreSQL / Neo4j / 各网关不可达时自动回退 SQLite / 内存图 / 模拟模式，绝不阻断启动

## 🧩 11 个 Agent 一览

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

## 📂 目录结构

- `src/` 后端（FastAPI 运行时 + 11 个 Agent + 网关 + 知识图谱 + 授权引擎）
- `studio/` 前端（React + Vite + Tailwind）
- `infra/` Dockerfile 与网关模拟器
- `scripts/` 种子 / 压测 / 验证脚本
- `docs/` 战略对齐与评估报告

## 📜 开源协议

[Apache License 2.0](LICENSE)。详见 [`NOTICE`](NOTICE)。

## 🤝 贡献

欢迎 Issue / PR。提交即表示同意以 Apache-2.0 协议贡献。
