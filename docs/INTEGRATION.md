# 系统集成指南：ERP / MES / PLM / WMS 对接

> 战略定位：智衍是**原生赋能者**，不推倒客户 ERP/MES，而是叠加「实时决策脑 + 全息真相源」。
> ERP/MES 退居**执行回写 + 审计桥**角色；智衍负责实时感知、推理与建议。

---

## 一、统一数据总线（DataSource Bus）

所有外部系统（网关 / MES / ERP / PLM / WMS / 时序库）都实现同一契约 `DataSource`：

```
ingest(values)           # 数据写入（网关实时流）
get_twin_state()         # 当前孪生态
is_available()           # 可达性（韧性降级）
query(q, **params)       # 按语义查询
fetch_recent(entity)     # 最近 N 条
health()                 # 健康状态
```

- 外部系统**不可达时自动降级**（seed/内存态），绝不阻断启动或 Agent 执行。
- 已实现连接器：`MESConnector` / `ERPConnector` / `PLMConnector` / `WMSConnector`（均继承 `RestConnector`）。

---

## 二、对接方式（env 注入，零代码）

在 `.env` 配置后即被 `load_sources_for_tenant()` 注入总线：

```bash
# MES（生产执行）
ZHIYAN_DS_MES_URL=http://mes.internal:8080/api
ZHIYAN_DS_MES_KEY=<mes-api-key>

# ERP（企业资源）
ZHIYAN_DS_ERP_URL=http://erp.internal/odoo/api
ZHIYAN_DS_ERP_KEY=<erp-api-key>

# PLM / WMS 同理（ZHIYAN_DS_PLM_* / ZHIYAN_DS_WMS_*）
```

按租户隔离：环境变量前缀 `ZHIYAN_DS_<租户大写>_MES_URL` 可给特定租户指定独立实例。

---

## 三、连接器 API 面（供 Agent 调用）

| 连接器 | 方法 | 语义 |
|--------|------|------|
| MES | `get_work_orders(status)` | 工单列表 |
| MES | `get_production_progress(wo_id)` | 工单进度 |
| MES | `get_quality_defects(line_id)` | 质量缺陷 |
| ERP | `get_purchase_orders(status)` | 采购订单 |
| ERP | `get_suppliers(material_code)` | 供应商 |
| ERP | `get_finance(period)` | 财务概览 |
| PLM | `get_bom(part_no)` / `get_parts()` | BOM / 物料 |
| WMS | `get_inventory(codes)` | 库存 |
| WMS | `get_shipments(direction)` | 出入库 |

Agent 通过 `registry.get(tenant_id, "mes")` 取连接器后调用，无需关心底层 HTTP。

---

## 四、数据流（实时决策闭环）

```
MES/ERP  ←── 轮询/Webhook  ──→  DataSource 总线
                                     │
                    网关实时流(UNS) ──┤──→ 孪生态 get_twin_state()
                                     │
                              Agent 推理（取数→分析→建议）
                                     │
                      建议/审批 ──→ 回写 ERP/MES（执行桥）
                                     │
                              审计日志（不可篡改留痕）
```

---

## 五、实施步骤（客户现场）

1. **盘点接口**：确认客户 MES/ERP 提供的 REST 端点与鉴权方式（API Key / OAuth2 / 企业微信）。
2. **配置总线**：在 `.env` 填入 URL/Key，重启 runtime，调 `/health/detailed` 看 `data_sources` 健康。
3. **字段映射**：若客户字段名与连接器默认不同，在 `connectors/domain.py` 子类覆写 `_get` 路径或加字段别名。
4. **回写试点**：选 1 个低风险动作（如库存预警通知）做**建议→人工审批→回写**，跑通审计桥。
5. **灰度扩大**：逐步开放自动执行（受 `AuthBoundary` 授权边界约束）。

---

## 六、韧性降级约定

- MES/ERP 不可达 → 该连接器 `is_available()=False`，Agent 自动改用 seed/内存态兜底数据，并标记结论 `stale`。
- 绝不因外部系统故障导致平台宕机或 Agent 500。

---

## 七、路线图（P1/P2）

| 能力 | 状态 | 说明 |
|------|------|------|
| REST 连接器（读） | ✅ 已实现 | MES/ERP/PLM/WMS |
| 网关实时流→孪生 | ✅ 已实现 | UNS + EnergyTwin |
| 回写/审计桥 | 🟡 设计中 | 建议→审批→ERP 回写 + 留痕 |
| 字段映射配置化 | 🟡 待做 | 改 YAML/DB 配置，免改代码 |
| 连接器模板库 | 🟡 待做 | 常见 MES(西门子/宝信)/ERP(用友/金蝶) 适配模板 |
| 国产化适配 | ⏳ 规划 | 信创环境（达梦/人大金仓） |

---

## 八、安全与合规

- 外部系统密钥仅存于 `.env`（gitignore），不进版本库。
- 回写操作必须经 `AuthBoundary` 授权边界 + 人工审批（高危动作默认人工）。
- 所有跨系统动作落审计日志，支持合规追溯。
