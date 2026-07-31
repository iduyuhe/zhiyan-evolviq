# 半导体晶圆厂设备接入指南

> **文档版本**：V1（2026-07-29）
> **策略**：先建模板不等待签约——客户接入时同型号设备直接套模板，数日完成
> **适用对象**：半导体晶圆代工/IDM 企业的数字化转型团队

---

## 一、快速接入流程

```
选定设备型号 → 查询本指南匹配 → 确认 OPC-UA 标签一致性 → 平台自动识别并启用推演
                                                                      ↓
                                                      PM 健康管理 ← 能耗碳排放 ← 设备级孪生
```

**从选定设备到看到第一个推演结论：预计 2-3 个工作日**（非 2-3 个月）。

---

## 二、预置设备模板库（6 大类 9 台设备）

### 2.1 光刻机（Lithography Scanner）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `scanner_1` | TWINSCAN NXT:1980Di | ASML | Health/LaserPower/OverlayNm/Vibration/ChamberTemp | 激光源寿命预测、套刻精度退化趋势、预防维护窗口建议 |
| `scanner_2` | TWINSCAN NXT:1980Di | ASML | 同上 | 同上（双机配置，独立健康跟踪） |

**接入前确认**：
- 设备支持 OPC-UA 协议（或通过 SECS/GEM 网关转换）
- 核心传感器标签可映射到 `ScannerX.Health`、`ScannerX.LaserPower` 等
- 非 ASML 光刻机（Nikon/Canon）需提供传感器映射表 → 快速适配

### 2.2 刻蚀机（Etcher）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `etcher_1` | Primo D-RIE | AMEC 中微 | Health/ChamberPressure/RFPower/EtchRateDev | 静电卡盘寿命预测、腔体压力异常告警、刻蚀速率偏差趋势 |
| `etcher_2` | 2300 Kiyo | Lam Research | Health/ChamberPressure/RFPower/EtchRateDev | 同上 |

**接入前确认**：
- 腔体压力传感器就位（mtorr 量级）
- 刻蚀速率偏差可实时读取（% 偏差）

### 2.3 薄膜沉积（Deposition）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `deposition_1` | Endura 300mm PVD | Applied Materials | Health/ChamberVacuum/HeaterTemp/TargetErosion | 靶材更换预警、真空泵寿命预测、沉积速率偏离检测 |
| `deposition_2` | Vector Express PECVD | Lam Research | Health/ChamberVacuum/HeaterTemp/RFPower | 射频发生器寿命、喷淋头堵塞预警 |

### 2.4 化学机械抛光（CMP）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `cmp_1` | Reflexion LK | Applied Materials | Health/PadTemp/PadLife/SlurryFlow/DownForce | 抛光垫换型预警、磨料泵异常、修整器寿命 |

### 2.5 检测/量测（Inspection）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `inspection_1` | 29xx 宽光谱 | KLA | Health/LaserSource/StagePrecision/DefectSensitivity | 激光源维护窗建议、光学系统清洁预警 |

### 2.6 离子注入（Ion Implanter）

| 模板 ID | 典型型号 | 供应商 | 关键 OPC-UA 标签 | 推演能力 |
|---|---|---|---|---|
| `implant_1` | VIISta 900 | Applied Materials | Health/BeamCurrent/BeamEnergy/SourceLife | 离子源寿命预测、束流退化警告、真空泵维护 |

---

## 三、如何匹配客户设备到模板

### 步骤一：确认设备类型

同一设备类型（光刻/刻蚀/沉积/CMP/检测/注入）可复用同一套推演逻辑。不同供应商的同一类型设备可能标签命名不同，但传感器语义一致。

### 步骤二：确认 OPC-UA 标签一致性

打开客户设备的 OPC-UA Server 地址 `opc.tcp://<设备 IP>:4840`，查看节点列表。

**自动匹配**：如果节点名包含 `Scanner`、`Etcher`、`Deposition`、`CMP`、`Inspection`、`Implant` 等关键词，系统自动匹配模板。

**手动映射**：如果标签命名不同，提供传感器映射表（示例）：

| 客户设备标签 | 模板标签 | 数据类型 | 单位 |
|---|---|---|---|
| `ns=2;s=LX1.Health` | `Scanner1.Health` | float | pct |
| `ns=2;s=LX1.LaserPwr` | `Scanner1.LaserPower` | float | pct |
| `ns=2;s=LX1.Overlay` | `Scanner1.OverlayNm` | float | nm |

### 步骤三：确认网关协议

| 协议 | 适用场景 | 模板覆盖 |
|---|---|---|
| OPC-UA | 新设备（ASML/AMAT/Lam 出厂标配） | ✅ 主推 |
| Modbus TCP | 老旧设备传感器扩展 | ✅ 支持 |
| SECS/GEM | 半导体行业标准（设备 → 主机） | ⏳ 开发中 |
| IPC-CFX | SMT 产线（非 Fab） | ✅ 支持 |

### 步骤四：启用推演

设备接入后，以下推演自动启动：

| 推演类别 | 延迟 | 产出 |
|---|---|---|
| ∑ 设备健康评分 | 接入后 5 分钟 | 各设备当前健康分、预警状态 |
| ⚙️ 预测维护 | 接入后 1 小时 | 高风险部件列表、建议维护时间窗口、备件预警 |
| ⚡ 设备级能耗 | 接入后 5 分钟 | 设备功率、周能耗、碳排放、节能机会识别 |
| 📊 设备基准对标 | 接入后 1 天 | 同类设备健康/能耗排名、异常偏差识别 |

---

## 四、异常处理

| 场景 | 行为 | 影响 |
|---|---|---|
| OPC-UA Server 不可达 | 自动回退 simulated 模式（基于模板默认值预测） | 推演继续，精度降低 |
| 标签不匹配 | 手动映射界面可在 1-2 小时内完成 | 推演延迟至映射完成 |
| 设备型号不在模板库 | 创建新设备类型模板，1-2 天 | 推演延迟至模板就绪 |
| 传感器部分缺失 | 缺失传感器用模板默认值占位 + 标注"置信度降低" | 推演继续，置信度标记 |
| 客户无 OPC-UA | 提供工业协议转换网关（现场部署） | 部署时间增加 1-2 天 |

---

## 五、费用参考

详见 `PRICING_MODEL.md`。设备接入本身不额外收费（包含在平台订阅/私有化费用内）。若需现场部署协议转换网关，按 Deploy as a Service ¥168,000 起计。

---

## 六、接入 Checklist（客户对接沟通用）

- [ ] 确定首批接入的设备型号、数量、位置
- [ ] 确认设备支持 OPC-UA 协议（或协议转换方案）
- [ ] 确认 OPC-UA Server 端点可达（TCP 4840 端口开放）
- [ ] 提供传感器标签列表（或现场 Demo 账号）
- [ ] 指定现场网络配合人（IT/自动化工程师）
- [ ] 约定接入时间窗口（建议非生产时间）
- [ ] 准备备份/回滚方案（平台侧双缓冲，不影响生产）
