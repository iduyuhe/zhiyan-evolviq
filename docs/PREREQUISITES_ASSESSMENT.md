# 智衍 EvolvIQ · 使用前提条件评估

> 评估日期：2026-07-25 | 视角：部署 / 数据 / 硬件 / 环境前提
> 方法：基于 `docker-compose.prod.yml`、`.env.example`、`pyproject.toml`、各 `Dockerfile` 与 `data/seed` 的真实配置审计

---

## 一、核心结论（一句话）

**门槛是"分层的"**：零数据、零真实源也能跑起来（种子 + 韧性降级），但要产生**真实业务价值**，硬前提是**一个 LLM API Key + 一份能对接的真实制造数据源**；硬件最低 4 核 8G，推荐 8 核 16G。

---

## 二、前提条件总览

| 维度 | 最低前提（能跑） | 实用前提（有用） | 关键程度 |
|:-----|:----------------|:----------------|:--------:|
| **数据** | 内置种子数据（SMIC 风格，17 文件） | 接 MES/ERP/SCADA 实时源 或 MCP/工业协议网关 | ★★★★★ |
| **LLM** | `LLM_API_KEY`（OpenAI 兼容） | 主通道 + 备用通道（混元等） | ★★★★★ |
| **数据库** | 留空 → 自动回退 SQLite | PostgreSQL 16（生产持久化） | ★★★☆☆ |
| **知识图谱** | 留空 → 自动回退内存图 | Neo4j 5（跨 Agent 知识） | ★★☆☆☆ |
| **运行时** | Python 3.13 + 浏览器 | Docker（生产全栈） | ★★★★☆ |
| **前端构建** | Node 22（构建 Studio） | 已构建静态产物 + nginx | ★★★☆☆ |
| **硬件** | 4 核 8G（演示） | 8 核 16G（生产） | ★★★☆☆ |
| **网络** | 单机 localhost | 对外 3006，容器间互访 | ★★★☆☆ |
| **人员** | 会 `docker compose up` | 懂制造业务 + 能对接数据源 | ★★★★☆ |

---

## 三、数据前提（用户重点）

### 3.1 零门槛起步 —— 种子数据开箱即用
`data/seed/` 已内置 **17 个真实风格种子文件**，覆盖全链路：

```
供应链：smic_bom.json / smic_inventory.json / smic_po.json / bom_npi_007.json / inventory.json / po_data.json
排程：   （APS 订单/工作中心，运行时生成）
设备：   pm_equipment.json
良率：   yield_data.json
质量：   quality_trace.json / aoi_results.json
工艺：   dfm_check.json / eco_cases.json / smic 风格
能耗：   （energy_carbon 内置模拟）
OTHERS： oee_lines.json / ipc_standards.json / components.json / metrics_demo.json
```

**含义**：不接任何外部系统，系统即用 SMIC 半导体产线数据演示全套能力（这也是上一轮实测齐套率 41.7%→100% 的数据来源）。

### 3.2 产生真实价值的前提 —— 对接数据源
当前工具层从 seed 加载，架构已留切换点。接真实数据的三条路径：

| 路径 | 接口 | 前提 | 工作量 |
|:-----|:-----|:-----|:------:|
| **工业协议网关** | Modbus / MQTT / OPC-UA / IPC-CFX | 现场有对应 broker/server（生产已带模拟器） | 中 |
| **MCP 联邦** | 38+ 工具 HTTP/stdio | 实现了 MCP server 的内部系统 | 中 |
| **MES/ERP API** | 直接改写 `tools.py` 数据源 | 有开放 API 或数据库读权限 | 高 |

**关键判断**：数据对接是"实用性从 7.5→9+"的唯一卡点（详见 PRACTICALITY_ASSESSMENT.md），工作量约 1–2 周/数据源。

### 3.3 数据格式与质量前提
- 结构化优先：BOM / 库存 / PO / 工单 / 设备台账最好已是结构化（JSON/DB 表）
- 非结构化（PDF 工艺卡、Excel）需先做抽取层
- 数据更新频率决定决策时效：日更够看板，分钟级才够实时干预

---

## 四、软件 / 运行环境前提

### 4.1 硬性版本（来自真实配置）
| 组件 | 版本 | 来源 |
|:-----|:-----|:-----|
| Python | **≥ 3.13** | `pyproject.toml:7` / `Dockerfile.runtime:5` (python:3.13-slim) |
| Node | **22-alpine** | `Dockerfile.studio:5` |
| PostgreSQL | 16-alpine | `docker-compose.prod.yml:73` |
| Neo4j | 5-community | `docker-compose.prod.yml:89` |
| RabbitMQ | 3-management | `docker-compose.prod.yml:141` |
| Mosquitto | 2 | `docker-compose.prod.yml:103` |
| Nginx | alpine（前端服务） | `Dockerfile.studio:15` |

### 4.2 Python 依赖（关键项，`pyproject.toml:10-30`）
```
fastapi, uvicorn, pydantic, sqlalchemy, asyncpg, aiosqlite
langgraph, langchain-core        # Agent 编排内核
openai                           # LLM 通道（硬前提）
mcp                              # MCP 联邦
pymodbus, paho-mqtt, asyncua, aio-pika   # 四类工业协议网关
neo4j                            # 知识图谱
apscheduler                      # 调度
```

### 4.3 三种使用模式的前提差异
| 模式 | 前提 | 适合 |
|:-----|:-----|:-----|
| **A. 演示 / POC** | `docker compose up`（全容器，含种子）+ LLM Key | 客户演示、培训 |
| **B. 本地开发** | Python 3.13 venv + Node 22（构建前端）+ LLM Key | 二次开发 |
| **C. 生产实时** | 模式 A + 对接真实数据源 + 运维能力 | 工厂落地 |

---

## 五、硬件 / 算力前提

### 5.1 生产全栈资源估算（10 容器）
| 服务 | 内存占用 | 说明 |
|:-----|:--------|:-----|
| neo4j:5-community | **2–4 GB** | 最大变量，可设空走内存图省掉 |
| rabbitmq:3-management | **1–2 GB** | Erlang VM 开销 |
| postgres:16 | 0.5–1 GB | |
| runtime (uvicorn) | 0.5–1 GB | langgraph 加载 |
| studio (nginx) | < 0.25 GB | 静态 |
| 4 个网关模拟器 | 各 < 0.25 GB | modbus/opcua/mqtt-pub/ipc-cfx |

**结论**：
- **最低（演示）**：4 核 8 GB —— 能跑，但 Neo4j+RabbitMQ 偏紧
- **推荐（生产）**：**8 核 16 GB** —— 舒适，留余量给网关与并发
- **降本技巧**：不需要知识图谱 → 不设 `NEO4J_URI`，省 2–4 GB；不需要 IPC-CFX → 不启 rabbitmq 相关服务

### 5.2 本地开发
- 仅跑 runtime（Python venv）+ 浏览器：2 核 4 GB 足够
- 跑全套 docker：同生产 8 GB 建议

---

## 六、网络 / 部署前提

### 6.1 端口矩阵（来自 `docker-compose.prod.yml`）
| 端口 | 服务 | 暴露 | 说明 |
|:-----|:-----|:------|:-----|
| **3006** | studio → 80 | **对外** | 唯一外部入口（前端 + /api 反代） |
| 8000 | runtime | 容器内 | studio nginx 反代 /api |
| 5432 / 7474 / 1883 / 5020 / 4840 / 5672 | 各依赖 | 容器内 | 容器间通信，无需对外放行 |

### 6.2 环境前提
- **OS**：Linux（腾讯云实测；macOS/Windows 开发可行，生产建议 Linux）
- **容器运行时**：Docker + docker compose v2
- **出网**：拉镜像需访问 Docker Hub / 国内镜像（已配清华/npmmirror 源）
- **LLM 出网**：runtime 需访问 `LLM_BASE_URL`（默认 OpenAI，可换国内兼容端点）
- **安全组**：生产环境放 22/80/3000-3005/3100（8080/8000 被丢弃，API 走 3006 内部代理）

---

## 七、组织 / 人员前提

| 角色 | 前提能力 | 是否必需 |
|:-----|:---------|:--------:|
| **部署运维** | 会 `docker compose up` / 看日志 | 必需（生产） |
| **业务配置** | 懂制造（供应链/排程/质量/设备） | 必需（发挥价值） |
| **数据对接** | 会写 API/DB 读取或 MCP server | 实用模式必需 |
| **最终用户** | 会用 Web 界面填目标、看结果 | 必需 |
| **算法/开发** | Python/TS，能扩 Agent | 可选（扩展时） |

**关键判断**：这套系统**不是"买来即用"的 SaaS**，而是**"平台 + 需配置"**——业务人员定义目标与授权边界，IT 对接数据源。纯业务人员独立部署有门槛，需 IT 配合。

---

## 八、韧性降级 —— "最低门槛"的真相

系统通过韧性降级（memory 铁律）把硬性前提降到最低：

- PostgreSQL 不可达 → **自动回退 SQLite**（不崩）
- Neo4j 不可达 → **自动回退内存图**（不崩）
- 任一网关不可达 → **simulated 模式**（不崩）
- LLM 不可达 → 规则计算仍跑，仅自然语言生成退化

**含义**：除 `LLM_API_KEY` 外，**没有任何外部依赖是"必须在线"才能启动的**。这让"先跑起来看效果"的门槛极低——一台 4 核 8G 云服务器 + 一个 LLM Key 即可。

---

## 九、给杜先生的落地检查清单

客户/用户部署前，逐条确认：

```
□ 有 OpenAI 兼容的 LLM_API_KEY（否则分析能力退化）
□ 有 Linux 服务器 ≥ 4C8G（演示）/ 8C16G（生产）
□ 已装 Docker + compose v2
□ 服务器能出网拉镜像 + 访问 LLM 端点
□ 对外放行 3006 端口
□ （实用）已识别至少 1 个可对接的真实数据源（MES/ERP/网关）
□ （实用）有懂制造业务的同事定义 Agent 目标与授权边界
□ （可选）需要知识图谱 → 预留 Neo4j 2-4G 内存
```

**一句话**：硬件和环境门槛很低（一台普通云服务器 + Docker），**真正的门槛是两个"软前提"——LLM Key 和数据对接能力**。前者花钱即可解决，后者是这套系统价值释放的关键杠杆。
