# 首客试点 + 真实设备接入 Runbook（阶段 6.2 · 攻击首客/真实场景空缺口）

> 配套：`PRODUCT_DEVELOPMENT_PLAN.md` §2.1(6.2) / `GAP_REVIEW_v29.md` 缺口 C
> 一句话：**北极星"决策实时化率"生产 ≈0%（仍 `ZHIYAN_DEMO_DATA=1`）**。本文件把"技术闭环"通向"商业闭环"——锁场景、接真设备、埋指标。

---

## 0. 为什么要现在做

| 事实 | 含义 |
|---|---|
| 阶段 0–5 技术 100% 闭环，但只在 simulated / demo 数据上验证 | 没在客户现场跑过一例真实设备 |
| 北极星 = 决策实时化率（实时孪生驱动÷总决策），MVP≥40% | 当前生产 ≈0%，因为喂的就是 demo 数据 |
| 战略头号楔子 = 经营层隐性 + 中国根 + SME 轻量 | 首客必须选**轻量、短 ROI、数据干净**的场景 |

---

## 1. 首客场景选项（待杜先生拍板）

| 候选 | 数据干净度 | ROI 速度 | 演示难度 | 推荐度 |
|---|---|---|---|---|
| **A. 设备健康 / 能耗孪生**（推荐） | 高（网关直接出） | 快（1–2 周见数） | 低 | ★★★ |
| B. 供应链风险协同 | 中（需 ERP 接） | 中 | 中 | ★★ |
| C. 排产建议看板 | 中（需 MES 接） | 中 | 中 | ★★ |

**推荐 A**：最短 ROI、数据最干净（网关流直接喂孪生体，不依赖滞后 ERP）、最易 demo——正好命中"不砸 ERP 获实时决策脑"的叙事。

---

## 2. 真实设备接入 Runbook（OPC-UA / MQTT）

> 复用 v21.0 的 `twin_feed` + UNS；生产无真设备时仍走 simulated 兜底（韧性降级铁律）。

### 2.1 OPC-UA 接入
1. 拿到设备端点 `opc.tcp://<host>:<port>` + 安全策略（None/Sign/Sign&Encrypt）。
2. 用 `gateway` 的 OPC-UA 适配器订阅节点（如 `ns=2;s=Line3.Oven1.Temperature`）。
3. 节点 → 孪生 tag 映射（沿用契约 `energy_kwh__<line_id>` / `power_kw__<line_id>` / `green_ratio__<line_id>`）：在 `EnergyTwinDataSource` config 里登记 `node_map`。
4. `registry.route_event("machine", values)` 上行 → UNS `gateway` 路 → 自动路由孪生体。
5. **连通性验证**（呼应 §4.4 铁律）：接入前先跑一次 `gateway.connect()` + 读 1 个节点，成功才保存配置。

### 2.2 MQTT 接入
1. broker `mqtt://<host>:<port>` + topic（如 `factory/line3/telemetry`）+ 认证（user/pw 或 cert）。
2. 订阅 → 解析 payload（扁平键）→ `route_event("machine", values)`。
3. 同样走 `node_map` 映射 + UNS。

### 2.3 韧性降级（必做）
- 设备/网关不可达 → 自动回退 seed 基线，孪生标 `stale`，agent 不崩（v21.0 T3 已实现）。
- 现场无真设备 → 仍可用 `simulated` 网关演示（当前生产即此态）。

---

## 3. 北极星埋点（把 0% 拉起来）

定义与落点：

| 指标 | 口径 | 埋点位置 |
|---|---|---|
| **实时化率** | 由 `real_time_*` 字段驱动、且含实时孪生上下文的决策数 ÷ 同期总决策数 | `engine` 出决策时标记 `used_twin_context: bool`；`/twin/dashboard` 聚合 |
| **孪生新鲜度** | `updated_at` 距今 < 300s 的孪生体占比 | `twin_state` 统计 |
| **隐性信号捕获量** | 单位时间入 UNS 的 human/social/meeting/collab 事件数 | UNS 计数 |

验收：试点跑通后，`/twin/dashboard` 应显示实时化率 > 0，且随真实设备数据流入爬升。

---

## 4. 试点验收清单

- [ ] 首客场景拍板（建议 A：设备健康/能耗孪生）
- [ ] ≥1 家试点签约 / 口头确认
- [ ] 真实 OPC-UA 或 MQTT 设备接入成功（含连通性验证）
- [ ] `energy_carbon.analyze()` 在该客户真实流下产出含 `real_time_*` 结论
- [ ] 北极星实时化率埋点上线，首个非零读数截图
- [ ] 1 页试点总结（场景 / 数据 / 客户收益 / 下一步）

---

## 5. 风险与对策

| 风险 | 对策 |
|---|---|
| 客户现场无标准协议 / 节点混乱 | 用 `node_map` 抽象；先 1 条产线试点，不铺开 |
| 真设备接入耗时超 1 周 | 先用 simulated 跑通链路，真设备并行对接 |
| 客户不愿接 ERP（怕改造） | 路线 A 不碰账本——只接网关流 + 写回审计桥，零 ERP 改造 |
| 数据合规 / 保密 | 多租户隔离 + 审批门；敏感字段脱敏 |

---

## 6. 执行版 · 动手步骤清单（照着做）

> 前面是"为什么 + 选型"，这节是"具体怎么动"。按 6.1→6.6 顺序走，每个勾完再下一项。

### 6.1 场景确认（杜先生拍板）
- [ ] 选定首客场景（**推荐 A：设备健康 / 能耗孪生**）
- [ ] 锁定 1 家试点（口头确认即可启动，合同后补）
- [ ] 选定 1 条产线 / 1 台关键设备作为数据源（建议：有温度/电流/能耗信号的设备，最易出孪生）

### 6.2 选网关（按设备能力二选一）
| 设备能力 | 选什么 | 备注 |
|---|---|---|
| 设备/PLC **原生支持 OPC-UA** | 直接用设备端点 `opc.tcp://<host>:<port>` | 最省事，零额外硬件 |
| 设备只给 **Modbus/私有协议** | 加 **OPC-UA 协议转换软件**（Kepware / Prosys OPC-UA Server）或边缘网关 | 把 Modbus 转成 OPC-UA |
| 设备/PLC **原生支持 MQTT** | 直接连 broker（EMQX / 设备自带） | topic 如 `factory/line3/telemetry` |
| 以上都没有 | 边缘盒子（树莓派 + Node-RED）做协议桥接 | 把任意串口/IO 转 MQTT/OPC-UA |

### 6.3 接线 + 节点映射（数据从设备到孪生体）
1. 网络通：网关机与设备在同一网段，能 `telnet <host> <port>` 通。
2. 订阅节点：列出要采的变量（如 `Line3.Oven1.Temperature`、`Line3.MainPower`）。
3. **节点 → 孪生 tag 映射**（在数据源 config 的 `node_map` 登记，沿用契约）：
   - `ns=2;s=Line3.MainPower` → `power_kw__line3`
   - `ns=2;s=Line3.EnergyTotal` → `energy_kwh__line3`
   - `ns=2;s=Line3.GreenRatio` → `green_ratio__line3`
4. **先验证再保存**（呼应 §4.4 铁律）：用 `gateway.connect()` + 读 1 个节点，成功才落配置。

### 6.4 服务器侧：从"演示"切"真实"
编辑生产服务器 `/root/zhiyan/.env`：
```ini
ZHIYAN_DEMO_DATA=0          # 关掉演示数据，改吃真实网关流
# 网关端点指向试点现场（若用默认 localhost 则无需改）
ZHIYAN_OPCUA_ENDPOINT=opc.tcp://<试点网关IP>:4840
# 或
ZHIYAN_MQTT_BROKER=<试点brokerIP>
```
然后重启：
```bash
cd /root/zhiyan && docker compose -f docker-compose.prod.yml up -d runtime
```

### 6.5 连通性验证（上线前必做）
登录系统 → 左侧「连接」tab → 网关区点"测试"，或：
```bash
curl -X POST -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{"protocol":"opcua","endpoint":"opc.tcp://<试点IP>:4840"}' \
  http://43.153.172.52:3006/api/connectivity/gateway
# 期望 {"ok": true, "latency_ms": ..., "mode": "live"}
```
> 若返回 `mode: simulated` 或 `ok:false`，说明仍走兜底/连不通——先排网络再继续。

### 6.6 看北极星"实时化率"从 0 爬起（验收截图）
1. 设备数据开始流入后，打开 `http://43.153.172.52:3006/` → 「孪生」tab（TwinDashboard）。
2. 应看到孪生体 `updated_at` 在动（新鲜度上升）、`real_time_*` 字段被填充。
3. 北极星实时化率 = 含实时孪生上下文的决策数 ÷ 总决策数，会从 **0%** 随真实流爬升。
4. **截图留存**：孪生面板 + 实时化率非零读数，作为试点首个证据。

### 6.7 产出 1 页试点总结（给客户/投融/生态用）
- 场景 / 接入设备 / 数据维度 / 客户收益（停机下降?能耗省?）/ 下一步放大计划。

---

*本 runbook 与 `ECOSYSTEM_LAUNCH.md` 互为表里：首客提供真实场景喂生态叙事，生态提供集成商加速首客落地。两者同步启动才能把 CCI 天花板从纸面拉到现实。*
