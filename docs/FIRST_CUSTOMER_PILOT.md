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

*本 runbook 与 `ECOSYSTEM_LAUNCH.md` 互为表里：首客提供真实场景喂生态叙事，生态提供集成商加速首客落地。两者同步启动才能把 CCI 天花板从纸面拉到现实。*
