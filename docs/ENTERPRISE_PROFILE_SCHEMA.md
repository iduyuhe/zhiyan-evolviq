# 企业现状描述接口 Schema 规范（两阶段实例化框架 · 第一阶段）

> 关联：`docs/MASTER_EXECUTION_PLAN.md` §1.6（顶层范式）、§3.7（研究案例模式）、§3.5（无感转型三圈解锁）
> 状态：规范稿（非产品代码）。本文件定义"企业入驻瞬间经声明式描述 + 凭证启动接口实例化"的数据契约，供后端 `ConnectivityPanel` / 多租户 RAG / 凭证 vault 实现对齐。
> 定调：2026-07-29 杜总确认 E2（先出规范，不写产品代码）；形态采用 D1 混合（结构化表单打底 + 自由描述补刀）。

---

## 一、目标与位置

两阶段实例化框架：

```
阶段一（公开预载活体）：案例库已预载行业智能 → 客户启用即见"某某行业分析"（免费外圈）
阶段二（客户专属实例）：企业经「现状描述接口」声明式描述 + 提供凭证
        → 系统推荐该开的集成接口 → 凭证实例化 → 组织/实体入租户 KG → 客户专属活体实例
```

本接口 = 阶段二的**驱动入口**。它决定"该实例化哪些接口、要什么凭证"，是 G 模式三圈解锁的"企业入驻叙事"翻译层。

---

## 二、接口形态：混合（D1 确认）

| 部分 | 形态 | 作用 |
|---|---|---|
| 结构化表单 | 下拉/填空（机器可驱动） | 驱动"同行业该开哪些接口"的推荐 |
| 自由叙述 | 自然语言文本框 | 补 agent 抽不出的隐性信息（战略意图/痛点/组织文化） |

agent 对自由叙述做抽取 → 结构化画像（复用 `tacit_capture` 抽取即锚定机制）。

---

## 三、Schema 字段定义

```yaml
EnterpriseProfile:
  # —— 基础画像（驱动行业锚定 + 案例库匹配）——
  industry:            enum[半导体, 3C, 新能源汽车, 通讯, 光伏, 工程机械, 其他]   # 必填，匹配案例库行业
  region:              string(max=60)        # 区域（省/市），用于区域行业标杆对标
  legal_entities:      list[string]          # 实际经营主体（法人实体），入租户 KG（真实体，非匿名）
  org_scale:           enum[<50, 50-200, 200-1000, 1000+]   # 组织规模
  revenue_band:        enum[<5000万, 0.5-2亿, 2-10亿, 10亿+] # 营收量级（仅内部校准用）

  # —— 现有 IT / OT 系统清单（驱动接口推荐）——
  systems:
    erp:               enum[用友, 金蝶, SAP, Oracle, 自研, 无] | null
    mes:               enum[自有, 第三方, 无] | null
    gateway:           list[enum[OPC-UA, Modbus, AMQP, MQTT, 无]]   # 工业网关协议
    social:            list[enum[企业微信, 钉钉, 邮件, 无]]          # 社交通道
    knowledge_base:    bool                  # 是否有现成知识库/RAG 素材

  # —— 数据接入意愿（映射三圈解锁）——
  intent:
    free_tier_ok:      bool=true             # 外圈免费（纯公开行业信号）默认可用
    internal_connect:  enum[暂不, 评估后, 现在就开]   # 中圈/内圈：给凭证接通内部
    concerns:          string(max=500)        # 合规/安全顾虑（驱动凭证 vault 红线说明）

  # —— 自由叙述（agent 抽取补刀）——
  narrative:           string(max=2000)       # 战略意图/痛点/组织文化等隐性信息

  # —— 凭证（阶段二触发，见第四节 vault 契约）——
  credentials:         CredentialVaultRef     # 引用，不含明文
```

---

## 四、凭证 Vault 契约（D2 铁律）

> 🔴 **凭证安全红线（杜总 2026-07-29 确认列为铁律）**：凭证**加密 vault 存储 + 租户隔离 + 绝不明文落库 / 绝不进日志 / 绝不进外发 payload**。

```yaml
CredentialVaultRef:
  vault_id:            string(uuid)          # 指向加密 vault 中密文，本接口不持明文
  kind:                enum[erp_writeback, gateway_opcua, social_wecom, social_dingtalk, email_imap]
  tenant_id:           string                # 租户隔离键（contextvars 单一真相源）
  # 明文仅在 runtime 内存中经 ensure_ready() 守卫临时取出使用，用毕不残留
```

- 拒绝任何把 `credentials` 明文写入 DB / 日志 / `/writeback` 回显 / `/environment` 外发接口。
- 凭证与 `legal_entities` 同属**私域数据**，须与案例库**公开推演**明确区分呈现（Q4 红线）。

---

## 五、描述 → 接口推荐（D3：驱动源 = 案例库）

案例库每条记录携带 `recommended_interfaces`（同行业客户入驻时驱动推荐）。匹配逻辑：

```
EnterpriseProfile.industry + systems
    → 查案例库同行业案例的 recommended_interfaces
    → 交差 systems 已填项 → 得出「建议开通 / 待补凭证 / 暂不需要」三态清单
    → 沿三圈解锁渐进：免费外圈默认开；中圈/内圈在 intent.internal_connect≠暂不 时引导给凭证
```

案例库 `recommended_interfaces` 字段示例（通讯行业中兴案例）：
`[policy(政策法规), market(原材料行情), benchmark(行业智能化对标), disclosure(公告披露·研究案例), erp_writeback(中圈), gateway_opcua(内圈)]`

---

## 六、合规闸门（Q2 红线，法律允许范围内）

- 自由叙述 `narrative` 与 `legal_entities` 属客户私域，发布前须过脱敏审核门（复用 §3.6 共生环审核机制）。
- 任何对外输出（含案例库匿名行业分析）发布前过**合规闸门**：agents 抽偏检查 + 杜总/团队终审。
- 🔴 一切在**法律允许范围**内做；可反推归因 + 结论偏差的风险点一律拦截，不碰法律。

---

## 七、与现有架构复用清单

| 本 schema 字段 | 复用现有 | 说明 |
|---|---|---|
| systems / credentials 录入 | `ConnectivityPanel`「连接」tab + `/data-sources/{kind}/test` 先测后存闸门（§4.4） | 扩展为"先填画像→系统推荐接口" |
| legal_entities / narrative 入 KG | 多租户 RAG + `tacit_capture` 抽取即锚定 | 私域实体基线 |
| credentials 实例化 | `connectors`（企微/钉钉/邮件）、`/writeback` ERP/MES 桥、网关 OPC-UA/AMQP | 凭证就位即开 |
| intent 映射 | §3.5 三圈解锁 + `ensure_ready()` 幂等守卫 | 渐进实例化 |

---

*本规范为两阶段实例化框架第一阶段的契约定义。产品代码实现前，后端/前端须以此 schema 为对齐基准。*
