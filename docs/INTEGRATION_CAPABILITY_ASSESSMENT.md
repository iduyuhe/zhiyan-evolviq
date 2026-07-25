# 智衍 EvolvIQ · 实战数据对接能力评估

> 评估日期：2026-07-25 | 视角：能接什么真实工业产品 / 接口方式 / 落地难度
> 方法：基于 `src/gateways/*`（4 类协议网关真实代码）、`src/runtime/mcp/federation.py`（MCP 联邦）、`data/seed` 与 `tools.py` 数据层的代码审计

---

## 一、对接能力总览（系统真实支持三层）

| 接入层 | 协议 / 方式 | 代码位置 | 提供什么 |
|:-----|:-------------|:---------|:---------|
| **工业协议网关** | Modbus TCP / MQTT / OPC-UA / IPC-CFX | `src/gateways/{modbus,mqtt,opcua,ipc_cfx}/` | 实时设备/产线数据（读+写） |
| **MCP 联邦** | HTTP `/mcp/tools` + stdio MCP server | `src/runtime/mcp/federation.py` | 65+ Agent 工具对外暴露（系统间调用） |
| **业务数据层** | 种子 JSON / PostgreSQL / 改写 `tools.py` | `src/agents/*/tools.py` | BOM/库存/工单/成本等经营数据 |

**关键事实**：4 类网关全部实现"惰性连接 + 失败回退 simulated"（见 `manager.py` 的 `_upgrade_loop`），即**接不上真实源也绝不崩**，可先演示再逐步接。

---

## 二、四类工业协议网关 → 真实产品映射 + 接口方式

> 说明：协议支持为**代码实测确认**；产品提供该协议为**工业事实**（OPC-UA=IEC 62541，Modbus/MQTT/IPC-CFX 均为行业通用标准，主流厂商原生支持）。

### 2.1 Modbus TCP —— 最普适，几乎什么设备都有
| 项 | 内容 |
|:---|:-----|
| **接口方式** | `host:port`（默认 5020，行业标准 502），`pymodbus`，读 coil / holding register（holding 值单位 ×100，读回 ÷100） |
| **真实产品（均提供 Modbus TCP 从站）** | PLC：西门子 S7-1200/1500（带 Modbus TCP）、施耐德 Modicon、三菱 Q/L、欧姆龙、台达；仪表：智能电表、温控器、流量计、变频器；边缘：有人/研华/摩莎串口服务器 |
| **对接难度** | ★☆☆☆☆（最易） |
| **适合** | 老旧设备改造、仪表采集、快速打通 |

### 2.2 MQTT —— IoT 平台与边缘网关标配
| 项 | 内容 |
|:---|:-----|
| **接口方式** | `broker:1883`（paho-mqtt），订阅主题如 `factory/line1/temperature`，支持 publish 下发控制；topic 命名需对齐 `factory/<line>/*` |
| **真实产品** | 工业 IoT 平台：阿里云 IoT、华为云 IoT、AWS IoT、ThingsBoard、EMQX；设备网关：研华 WISE、有人 USR、树莓派边缘；部分变频器/仪表带 MQTT |
| **对接难度** | ★★☆☆☆ |
| **适合** | 已上云的设备、边缘网关汇聚后的数据 |

### 2.3 OPC-UA —— 现代 PLC/SCADA 原生标配（工业标准）
| 项 | 内容 |
|:---|:-----|
| **接口方式** | `opc.tcp://host:4840`（asyncua），节点读/写（NodeId 形如 `ns=2;s=Line1.OvenTemp`）；**支持读+写（控制指令）** |
| **真实产品（均原生提供 OPC-UA Server）** | PLC/SCADA：西门子 SIMATIC、罗克韦尔 FactoryTalk、B&R、倍福 TwinCAT、欧姆龙；工业软件：KEPServerEX（PTC）、Ignition、WinCC、iFIX；设备：多数现代 CNC/机器人/仪器 |
| **对接难度** | ★★★☆☆（需节点地址映射，但主流全支持） |
| **适合** | 新建产线、标准 SCADA 对接、需要双向控制的场景 |

### 2.4 IPC-CFX（IPC-2591）—— 电子/SMT 制造专属标准
| 项 | 内容 |
|:---|:-----|
| **接口方式** | AMQP 1.0 总线（aio-pika），RabbitMQ broker，订阅 `CFX.*` 事件（`CFX.Production.TestResults` / `EquipmentStatusChanged` / `MaterialCarrierLoaded` 等） |
| **真实产品（原生 CFX 或 Hermes）** | SMT 设备：ASM Siplace/DEK、Kohyoung（SPI/AOI）、Omron、Yamaha、Fuji、Panasonic；MES：支持 Hermes/CFX 的车间 MES、西门子 Insights Hub |
| **对接难度** | ★★★☆☆（电子制造标准，需产线已上 CFX/Hermes） |
| **适合** | SMT/半导体产线、电子组装车间（与 supply_chain / aoi_judge / smt_changeover 强相关） |

---

## 三、MCP 联邦 → 系统间能力对接

| 项 | 内容 |
|:---|:-----|
| **接口方式** | HTTP `POST /mcp/tools/{name}/call`（命名空间 `agent__method`），或 stdio MCP server；`list_tools` 暴露 65+ 工具规格 |
| **能力清单** | 20 个 Agent × 3+ 工具（query + action），如 `supply_chain__get_bom`、`aps_scheduler__rebalance_schedule`、`energy_carbon__create_saving_task` |
| **可对接系统** | 任何 MCP client（Claude Desktop / Cursor / 自研 Agent / 上层编排系统）、或经 HTTP 调用的内部系统 |
| **实战价值** | 把智衍的 20 个工业 Agent 能力暴露给上层 Agent / 编排系统，成为"能力货架" |
| **对接难度** | ★★☆☆☆（标准 MCP 协议） |

---

## 四、业务系统对接（MES / ERP / 数据库）

| 项 | 内容 |
|:---|:-----|
| **接口方式 A** | 改写 `src/agents/*/tools.py` 数据源：从 seed JSON → 调用 REST API / 直连 SQL |
| **接口方式 B** | 经 MCP server 包装内部 API（由联邦层暴露） |
| **可对接产品** | ERP：SAP、用友、金蝶、鼎捷、Oracle；MES：宝信、石化盈科、自研 MES、西门子 Insights Hub；数据库：PostgreSQL / MySQL / SQL Server 直连读 |
| **对接难度** | ★★★★☆（取决于对方 API 开放度，需开发） |
| **适合** | 订单/库存/成本/供应商等经营数据实时化 |

---

## 五、对接能力矩阵（常用产品 × 支持协议）

| 真实产品 | Modbus | MQTT | OPC-UA | IPC-CFX | 对接路径 |
|:---------|:------:|:----:|:------:|:-------:|:---------|
| 西门子 SIMATIC PLC | ✅ | ✅ | ✅ | — | OPC-UA（首选）/ Modbus |
| 罗克韦尔 PLC | ✅ | ✅ | ✅ | — | OPC-UA |
| 施耐德/三菱/欧姆龙 PLC | ✅ | ✅ | ✅ | — | Modbus / OPC-UA |
| 智能电表/温控器/变频器 | ✅ | 部分 | — | — | Modbus（最易） |
| 阿里云/华为云 IoT | — | ✅ | — | — | MQTT |
| ThingsBoard / EMQX | — | ✅ | — | — | MQTT |
| KEPServerEX / Ignition | ✅ | ✅ | ✅ | — | OPC-UA（聚合多源） |
| ASM/Kohyoung/Yamaha SMT | — | ✅ | ✅ | ✅ | IPC-CFX（电子专属） |
| SAP/用友/金蝶 ERP | — | — | — | — | REST API / DB（tools.py） |
| 宝信/自研 MES | — | ✅ | ✅ | ✅ | MQTT/OPC-UA/IPC-CFX + API |

---

## 六、实战对接落地指引（按场景）

| 你的数据源 | 推荐协议 | 接口方式 | 工作量 |
|:-----------|:---------|:---------|:------:|
| 车间 PLC/仪表实时数据 | OPC-UA 或 Modbus | 填 endpoint / host:port | 0.5–2 天 |
| 已上云的设备（IoT 平台） | MQTT | 填 broker:1883 + 对齐 topic | 1–2 天 |
| SMT/半导体产线 | IPC-CFX | 填 amqp broker + 订阅 CFX.* | 2–3 天 |
| 订单/库存/成本（经营） | MES/ERP API | 改写 tools.py 或 MCP 包装 | 1–2 周 |
| 上层 Agent 编排调用智衍 | MCP 联邦 | HTTP /mcp/tools 或 stdio | 1–3 天 |

---

## 七、关键结论

1. **协议层是"工业标准全覆盖"**：Modbus / MQTT / OPC-UA / IPC-CFX 都是主流工业协议，**几乎所有现代工业产品都原生提供这些接口**（尤其 OPC-UA 已成 PLC/SCADA 标配）。不存在"产品不支持接不进"的问题。
2. **真正的对接工作量不在协议，在映射**：节点地址 / topic 命名 / 字段对齐（占 70%），以及 MES-ERP 的 API 开发（占其余）。
3. **韧性降级让对接"渐进式"**：先 simulated 跑通演示 → 接一个真实源验证 → 逐步扩。无需一次性全接。
4. **MCP 联邦补齐"系统间"短板**：除接设备/业务系统，还能被上层 Agent 编排系统调用，定位为"工业 Agent 能力货架"。
5. **落地杠杆**：对 90% 制造企业，最快产生价值的路径是 **OPC-UA（产线）+ MQTT（IoT 平台）** 两条，1 周内可见实时数据驱动的分析。
