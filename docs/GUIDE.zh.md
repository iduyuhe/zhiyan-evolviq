# 智衍 EvolvIQ · 应用指南

> 如何快速上手 20 个工业 Agent，从目标设定到结果解读的全流程操作手册。

---

## 一、快速上手

### 1.1 访问平台

**生产环境**：`http://43.153.172.52:3006`

**本地开发**：
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # 填入 LLM_API_KEY
python -m src.runtime.main
# 打开 http://localhost:8000 或使用前端: http://localhost:8080
```

**Docker 一条命令**：
```bash
docker compose up -d        # 全栈含 PG+Neo4j+前端
```

### 1.2 选择 Agent

页面右上角的 **Agent 选择器** 展示全部 20 个 Agent，按 5 大场景分组：

| 场景 | 图标 | 包含 Agent |
|------|:----:|-----------|
| 供应链指挥官 | 📦 | supply_chain |
| 研发加速器 | 🔬 | dfm_check / bom_selector / eco_change |
| 产线管家 | ⚙️ | pm_maintenance / oee_optimizer / smt_changeover / aoi_judge |
| 质量侦探 | 🛡️ | yield_analysis / quality_trace / ipc_standard |
| 经营决策 | 🧠 | aps_scheduler / energy_carbon / cost_analysis / demand_order / wms_logistics / compliance_q / executive_cockpit / rd_npi / procurement_manage |

> 选择任一 Agent 后，输入框下方会自动显示该 Agent 的 3 个示例目标，一键填入。

### 1.3 设定目标

在输入框中用**自然语言**描述你想要的工业分析任务，例如：

- **供应链**：「检查 SMIC-28nm-Logic BOM 的物料供应情况，重点关注国产替代方案」
- **计划排程**：「分析全部工单的生产排程与产能负荷，识别瓶颈和交期风险工单」
- **质量合规**：「检查 ISO 9001、IATF 16949 等质量体系认证状态，对高风险发现自动生成 CAPA」

> 不需要特定关键词或格式——用你平时说话的方式告诉 Agent 你要什么。

### 1.4 阅读结果

Agent 返回的结果按 Tab 分页展示，典型的 Tab 结构：

| Tab | 内容 |
|-----|------|
| **总览** | 顶部 4 张指标卡 + 一段总结文字 |
| **明细** | 逐项数据（工单/产品/物料/供应商等） |
| **风险/动作** | 高风险项列表 + 授权内已自动执行的动作 |

每个动作都会标注 `✅ 已自动执行`（授权内）或 `⏳ 待审批`（需人工确认）。

---

## 二、20 个 Agent 应用场景速查

### 2.1 供应链（supply_chain 📦）

**典型目标**：
- 「每2小时检查28nm产线物料齐套，硅片/光刻胶/特种气体缺料风险>30%时自动检索替代方案」
- 「检查SMIC-28nm-Logic BOM的物料供应情况」

**自动动作**：确认PO（自动）、锁定替代（授权内自动或待批）

### 2.2 设备维护（pm_maintenance 🔧）

**典型目标**：
- 「检查SMIC光刻机和刻蚀机的设备健康状态，列出需要关注的高风险部件」
- 「查看薄膜沉积设备的预防维护计划和备件更换建议」

### 2.3 良率分析（yield_analysis 📈）

**典型目标**：
- 「分析28nm逻辑产品的良率趋势和缺陷分布，找出主要原因」
- 「对比光刻机#1和#2的良率差异，定位低良率设备」

### 2.4 质量追溯（quality_trace 🔍）

**典型目标**：
- 「追溯28nm产品边缘颗粒污染超标的质量问题，从客诉追溯根因」
- 「对近期质量异常批次进行追溯分析，找出共性根因」

### 2.5 DFM 检查（dfm_check 📐）

**典型目标**：
- 「对PCB-A-v3.2进行全板DFM检查，焊盘间距/线宽/阻焊覆盖全面审查」
- 「检查电源模块的DFM可制造性，重点关注载流能力」

### 2.6 BOM 选型（bom_selector 🔬）

**典型目标**：
- 「查找STM32F407VGT6的pin-to-pin兼容替代料，优先国产方案」
- 「推荐MCU选型，要求ARM Cortex-M4/1MB Flash/LQFP-100封装」

### 2.7 OEE 优化（oee_optimizer ⚡）

**典型目标**：
- 「分析全部SMT产线的OEE，找出瓶颈产线和六大损失分布」
- 「查看SMT-L02产线OEE低于目标的原因，给出改善建议」

### 2.8 ECO 变更（eco_change 🔄）

**典型目标**：
- 「分析ECO变更：U12 MCU由STM32F407切换为GD32F407的影响范围」
- 「评估阻焊层厚度从15um改为20um的工程变更影响」

### 2.9 SMT 换线（smt_changeover 🔀）

**典型目标**：
- 「生成SMT-L01从PCB-A切换到PCB-C的换线计划，SMED优化」
- 「分析SMT-L02换线时间过长的原因，给出SMED改善建议」

### 2.10 AOI 判定（aoi_judge 👁）

**典型目标**：
- 「分析SMT-L01产线AOI误报率，给出阈值优化建议」
- 「优化AOI检测参数，目标将误报率从75%降至25%」

### 2.11 IPC 标准（ipc_standard 📋）

**典型目标**：
- 「查询BGA焊球空洞在IPC-A-610标准下的可接受范围」
- 「判定Chip组件偏位在不同Class下的可接受标准」

### 2.12 计划排程（aps_scheduler 🧠）

**典型目标**：
- 「分析全部工单的生产排程与产能负荷，识别瓶颈和交期风险工单」
- 「评估SMT产线2高负荷对交期的影响，给出产能再平衡建议」

**自动动作**：rebalance_schedule（产能再平衡）✔
**待审批**：expedite_order（加急工单）⏳

### 2.13 能源碳 ESG（energy_carbon 🌿）

**典型目标**：
- 「核算本周各产线能耗与碳排放，识别低绿电高耗能环节」
- 「评估空压机能效改造和绿电采购的降碳潜力与回收期」

**自动动作**：create_saving_task（生成节能降碳任务）✔

### 2.14 制造成本（cost_analysis 💰）

**典型目标**：
- 「拆解28nm逻辑芯片的单位制造成本，定位超目标成本的科目」
- 「分析国产替代料与良率提升可带来的降本空间」

**自动动作**：create_cost_reduction（生成降本任务）✔

### 2.15 需求订单（demand_order 📊）

**典型目标**：
- 「分析本季各产品的需求预测与已接订单，识别未交付与交期风险」
- 「对比需求与产能，给出28nm逻辑芯片的交期承诺与产销协同建议」

**自动动作**：reallocate_supply（供给再平衡）✔
**待审批**：expedite_order（加急订单）⏳

### 2.16 仓储物流（wms_logistics 🚚）

**典型目标**：
- 「分析关键物料库存健康度，识别低于安全库存的物料并自动补货」
- 「统计各物流路线的时效与准时率，定位慢链路改道建议」

**自动动作**：create_replenishment（自动补货）✔
**待审批**：reroute_shipment（物流改道）⏳

### 2.17 质量合规（compliance_q 🛡️）

**典型目标**：
- 「检查ISO 9001、IATF 16949等质量体系认证状态，识别到期风险和审核发现」
- 「追踪RoHS/REACH等法规合规状态，对高风险发现自动生成CAPA纠正措施」

**自动动作**：create_capa（生成CAPA纠正措施）✔
**待审批**：escalate_compliance（合规升级）⏳

### 2.18 经营驾驶舱（executive_cockpit 🏢）

**典型目标**：
- 「汇总本季经营KPI：营收、毛利率、净利润、现金流，定位超预算部门并生成改善项」
- 「分析各产品产出完成率与预算执行差异，给出经营决策建议」

**自动动作**：create_action_item（生成改善行动项）✔
**待审批**：approve_budget_adjustment（预算调整审批）⏳

### 2.19 研发新产导入（rd_npi 🔬）

**典型目标**：
- 「检查各NPI项目进度与里程碑，识别高风险和延迟项目，自动生成加速推进建议」
- 「查看BMS控制器R3的里程碑明细，分析延迟根因并给出纠正行动」

**自动动作**：expedite_project（加速推进）✔
**待审批**：reprioritize_project（项目重新排优先级）⏳

### 2.20 采购与供应商管理（procurement_manage 📑）

**典型目标**：
- 「分析供应商绩效，识别低评分供应商并自动生成供应商评审任务」
- 「查看合同到期与采购策略执行进度，给出合同续签建议」

**自动动作**：create_supplier_review（供应商评审）✔
**待审批**：renegotiate_contract（合同重新谈判）⏳

---

## 三、策略调参（授权控制台）

### 3.1 访问

页面导航 → **🎚️ 策略调参** Tab。

### 3.2 调什么

| 旋钮 | 作用 | 范围 |
|------|------|:----:|
| **confidence_threshold** | 置信度阈值——Agent 多自信才允许自主执行 | 0.50 ~ 0.95 |
| **max_daily_autonomous** | 每日自主上限——该 Agent 一天可自动执行几次 | 0 ~ 50 |

### 3.3 什么时候调

| 现象 | 建议操作 |
|------|---------|
| Agent 太保守，太多动作送到审批 | 降低 confidence_threshold（放权） |
| Agent 太激进，批准确认率低 | 提高 confidence_threshold（收紧） |
| Agent 表现稳健且高批准率 | 提高 max_daily_autonomous（提上限） |

### 3.4 效果指标

| 指标 | 含义 |
|------|------|
| 自主率 | Agent 自主执行的动作占比（越高=越放权） |
| 批准率 | 送审动作中人工批准的占比（越高=人类越信任） |
| 驳回率 | 送审动作中人工驳回的占比（越高=Agent 判断不准） |

---

## 四、网关监控

### 4.1 访问

页面导航 → **🛰️ 网关** Tab。

### 4.2 查看什么

- 4 类网关的状态（就绪 / 模拟 / 断开）
- 实时读数（每 4 秒自动刷新）
- 模式标识：`real`(真实数据源) vs `simulated`(模拟模式)

### 4.3 网关列表

| 网关 | 协议 | 典型数据点 |
|------|------|-----------|
| Modbus | RTU/TCP | 线速度、温度、压力、能耗 |
| MQTT | Pub/Sub | 设备告警、状态事件 |
| OPC-UA | 统一架构 | 设备健康、工艺参数 |
| IPC-CFX | 行业标准 | 测试结果、物料载入、设备状态变更 |

---

## 五、知识图谱

### 5.1 访问

页面导航 → **🧠 知识图谱** Tab。

### 5.2 能力

- **统计总览**：节点数、边数、模式（neo4j / memory）
- **跨 Agent 桥接**：质量案例→设备→部件→产线的端到端关联
- **增量写入**：Agent 执行结果自动作为新边写入图谱

### 5.3 示例查询

```
查询与 scanner_1 相关的所有节点与边
→ 返回 Equipment(scanner_1) → Part → Alert → QualityCase 的关联链路
```

---

## 六、部署与运维

### 6.1 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM 推理层密钥 | (必填) |
| `ZHIYAN_DB_URL` | 数据库连接 | PostgreSQL > SQLite 自动回退 |
| `ZHIYAN_DEMO_DATA` | 是否注入演示数据 | 0=关闭, 1=开启 |
| `X-Tenant-Key` | 多租户标识（HTTP 头） | 不传则默认 `default` |

### 6.2 韧性降级（自愈行为）

| 依赖 | 不可达时 | 恢复后 |
|------|---------|--------|
| PostgreSQL | 自动回退 SQLite 文件 | 下次启动自动切回 PostgreSQL |
| Neo4j | 自动回退内存邻接表 | 重建图谱自动切回 Neo4j |
| OPC-UA Server | 模拟模式（本地种子数据） | 连接恢复自动切换 live |
| AMQP Broker | 模拟模式（本地事件队列） | 连接恢复自动切换 live |

> **绝不阻断启动或执行管道**——任何一个外部依赖的故障都不会让平台宕机。

### 6.3 Docker 全栈部署

```bash
git clone https://github.com/iduyuhe/zhiyan-evolviq.git
cd zhiyan-evolviq
cp .env.example .env          # 填入 LLM_API_KEY
docker compose up -d           # 全栈: postgres+neo4j+mosquitto+modbus+opcua+rabbitmq+runtime+studio
```

访问 `http://localhost:8080` 即可使用。

---

## 七、常见问题

### Q: 为什么 Agent 返回说"无法识别"？

Router 未匹配到合适的 Agent。尝试在目标中增加更明确的关键词（如"供应链""排程""碳"等），或手动从 Agent 选择器选择对应 Agent。

### Q: Agent 自动执行的动作安全吗？

所有自动动作都在**授权边界**内执行——每 Agent 有独立的 `confidence_threshold` / `max_daily_autonomous` / 白名单限制。高风险动作（加急订单、重新谈判合同等）强制送人类审批。

### Q: 种子数据和生产数据怎么切换？

当前所有 Agent 读取 `tools.py` 中硬编码的种子数据。切换到生产数据只需将工具层的数据源改为从真实 ERP/MES/SCADA API 读取即可，**Agent 分析逻辑不变**。

### Q: 可以用自己的 LLM 吗？

可以。`src/common/llm_client.py` 是 OpenAI 兼容接口，支持任意 OpenAI 兼容 API（包括本地 vLLM、Ollama）。只需在 `.env` 中配置 `LLM_API_BASE` 和 `LLM_API_KEY`。

### Q: 怎么添加一个自定义 Agent？

参照现有 Agent 结构（如 `src/agents/cost_analysis/`），实现 `BaseAgent.analyze(goal)` 契约，然后在 4 处注册（`router.py` 注册表 + `engine.py` 规划元组 + `federation.py` 工具 + `authorization.py` 边界），最后加前端渲染即可。
