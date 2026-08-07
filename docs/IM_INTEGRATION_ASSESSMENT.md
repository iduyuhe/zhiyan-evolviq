# 智衍 × IM 对接评估（借鉴 OpenClaw「Agent↔即时通讯」范式）

> 触发：杜总「评估借鉴 OpenClaw 与 IM 的对接，能否用于移动端审核与查询」。
> 日期：2026-08-04　|　性质：架构评估（未动代码）　|　结论：**可借，且对智衍的价值高于对 OpenClaw 本身**。

---

## 0. 结论先行（ verdict ）

1. **范式可迁移，且不是 OpenClaw 专有**。IM 对接的本质是通用架构：
   `IM 消息回调 → 意图路由 → 调 Agent → 回卡片/图文；交互卡片按钮 → 回调 → 触发动作`。
   这套架构与具体 IM（企微/飞书/钉钉）无关，差异只在回调协议与卡片格式。智衍可直接采用。
2. **对智衍比 OpenClaw 更值**。智衍的产品重心是**人留终审 + 审批闸门（L3 门禁、bid_intel 终审、多 Agent approve）**——这正是 IM 交互卡片最擅长的移动场景。OpenClaw 是消费级技能市场，没有这套工业治理刚需。
3. **智衍已有 70% 地基**，缺的是"入站（inbound）半边"：消息回调 + 验签 + 意图路由 + 审批卡片。不是从零，是补半边。

> ⚠️ **诚实边界**：本评估基于智衍现有 `WeComService` 代码与 OpenClaw 通用架构推理。我手头**无 OpenClaw 的实际 IM 接入代码/协议**。若杜先生能分享 OpenClaw 怎么接 IM（回调协议 / 卡片格式 / 会话维持），我可以做 1:1 映射。但下面的可行性与路径不依赖那份细节。

---

## 1. 两种 IM 对接范式对比

| 维度 | 范式 A：H5 容器（智衍现有） | 范式 B：对话 + 卡片（OpenClaw 类） |
|---|---|---|
| 形态 | 在企微内置浏览器打开完整 H5 | 在 IM 会话里发消息/收卡片 |
| 查询 | 打开 App 用全套驾驶舱 | 发一句"XX 产线良率？"→ 回答案 |
| 审核 | 进 App 找待审项、点通过 | 收到审批卡片，直接点「通过/驳回」 |
| 适合 | 富交互、复杂决策看板 | 轻量快问 + 移动审批 |
| 智衍现状 | ✅ 已建（免登 + 推送） | ❌ 未建（缺回调/卡片） |

**关键判断**：范式 A 与 B 不是替代，是互补。H5 管"重决策看板"，IM 管"通知 + 审批 + 快问"。用户要的"移动端审核与查询"，范式 B 是更顺手的那一半。

---

## 2. 智衍现状盘点（基于 `src/runtime/wecom/` + 测试）

**已具备（outbound 半边，已测、优雅降级、凭证脱敏）**
- `WeComService`：`get_access_token`(缓存) / `get_jsapi_ticket` / `sign_agent_config`(免登签名) / `send_app_message`(textcard 单向推送)。
- API：`/wecom/status`、`/wecom/jsapi-signature`、`/wecom/push`。
- 免登（agentConfig）已就绪；缺料预警类单向推送已可接线。

**缺失（inbound 半边，指南明确标注"第二阶段未含"）**
- ❌ 消息/事件**回调端点**（`/wecom/callback`）+ Token/AESKey **验签**。
- ❌ **意图路由**：入站文本 → 哪个分身/会话。
- ❌ **交互式审批卡片**（template_card 按钮）→ 回调触发动作。
- ❌ **WeCom userid ↔ 智衍租户/角色**绑定（免登给了身份，但对话场景需解析到内部 user → 角色 → 能力过滤，复用 `_filter_sub_tasks_by_capability`）。

---

## 3. 平移可行性：缺什么、复用什么

| 需要的能力 | 智衍是否已有可复用 | 需新建 |
|---|---|---|
| 企微凭证/token/签名 | ✅ `WeComService` | — |
| 租户上下文 / 鉴权 | ✅ `context.py` + JWT + X-Tenant-Key | — |
| Agent 执行 / 多 Agent 编排 | ✅ `MultiAgentOrchestrator` + `/sessions/multi-agent` | — |
| 人留终审 / 审批门 | ✅ `/{id}/approve-multi` + bid_intel 终审 + 权限第③层 | 把审批**暴露成卡片按钮** |
| 消息回调 + 验签 | ❌ | 🔴 新建（企微特定，不能抄 OpenClaw） |
| 意图路由 | ❌ | 新建（轻量：关键词/指令前缀） |
| 审批卡片 + 按钮回调 | ❌ | 新建（template_card） |
| 零真名回复过滤 | ⚠️ 后端有 `_assert_no_leak`，需**显式接进 IM 回复链路** | 接线 |

**一句话**：执行层、治理层、凭证层都现成；要补的是"IM 入口管道"——回调验签 + 路由 + 卡片，约 1 个中等模块，不碰既有 Agent/前端。

---

## 4. 审核场景价值（最高 ROI，建议 Phase A 先做）

智衍的「人留终审」现在需要一个移动审批面。企微交互卡片天然契合：
- 触发：bid_intel 终审 / 多 Agent `approve-multi` / L3 授权门 待审时 → 推 `template_card`（标题+摘要+「通过/驳回」按钮）。
- 动作：责任人点按钮 → 企微回调 → 后端验签 → 调现有 `/{id}/approve-multi`（或 bid_intel 终审端点）+ 权限第③层复检 → 记录审计。
- 价值：**凌晨收到缺料/中标风险，手机点一下即终审**，比进 H5 找待审项顺手一个数量级。直接服务产品红线「分身不代签、人留终审」。

---

## 5. 查询场景价值（Phase B，对齐 G 模式）

- 入站文本 → 意图路由 → **只读**调一个分身（经营管控/行业洞察）→ 回图文卡片。
- **只读优先、禁 L3 自动执行**：对外只承诺 L0–L2（见 `EXTERNAL_NARRATIVE.md` §3），IM 查询只给"判断/预案"，不给"已执行"。
- 战略契合：IM 可作**外圈免费入口**——产业/行业级洞察免费问，企业级深度集成仍回 H5/付费。把 G 模式"注册即获得感"延伸到聊天框。

---

## 6. 风险与铁律（必须前置，不能事后补）

1. 🔴 **回调验签强制**：企微要求 Token/AESKey 验签，OpenClaw 的鉴权不等于企微的——**必须按企微协议自己实现**，不可照搬。
2. 🔴 **零真名延伸到 IM**：回复进个人会话，泄密面比 H5 大。所有 IM 出站文本必须过 `_assert_no_leak()`，real_anchor/客户真名绝不进卡片。
3. 🔴 **租户隔离**：一个企微 corp = 一个租户；多租户需 corp-id → tenant 路由，复用 X-Tenant-Key fail-closed。
4. **别把 IM 当完整前端**：IM = 通知 + 审批 + 快问；富决策驾驶舱仍在 H5/App。避免用聊天替代看板。
5. **会话上下文**：初版可无状态（每条消息独立意图）；如需多轮，复用现有 session 机制，勿在 IM 层另造会话栈。

---

## 7. 建议落地路径（接入「移动端三阶」第②阶增强）

| 阶段 | 内容 | 复用 | 工作量 |
|---|---|---|---|
| **Phase A（优先）** | 审批卡片：把现有 approve 端点暴露成企微 template_card 按钮 → 回调触发 | `approve-multi` / bid_intel / 权限③层 / `WeComService.send` | 中（新建 callback+验签+卡片） |
| **Phase B** | 只读查询：入站文本 → 路由 → 只读分身 → 回卡片 | Orchestrator / 分身 / `_assert_no_leak` | 中 |
| **Phase C（可选）** | 双向会话 + 上下文 + 多轮 | session 机制 | 大 |

> 该路径是「移动端三阶」第②阶（企微自建应用 H5）的**增强**——企微不止当 H5 容器，而是"对话 + 审批"移动前端，位于小程序（第③阶）之前/并行。

---

## 8. 待杜总拍板 / 补充（原评估，落地时部分已自动澄清）

1. 是否共享 OpenClaw 的 IM 接入细节（回调协议/卡片格式），以便 1:1 映射而非按企微通用协议重做？
2. Phase A 的审批卡片先接哪条终审链（bid_intel 中标终审 / 多 Agent approve / 缺料门）？
3. IM 查询是否先锁"只读 + 外圈免费"口径，避免过早放开 L3？

---

## 9. 实现状态（2026-08-03 落地 · Phase A + Phase B 全刀完成）

> 评估阶段认为"inbound 半边缺失"，落地时发现**地基比评估预期更完备**：`wecom_ingest.py` 已有 Token/AESKey 验签 + AES-256-CBC 解密，`connectors.py` 已有免 JWT 的 `/connectors/wecom/callback`。故实际新建的是"绑定 + 卡片 + 路由 + 零真名过滤"，未重复造轮子。

### 9.1 已落地（代码 + 19 测全绿）
| 能力 | 模块 / 端点 | 复用 |
|---|---|---|
| 零真名单一真相源 | `src/common/leak.py`（从 `compliance_reviewer` 抽出 `LEAK_TOKENS` + `sanitize_leak`） | 出站过滤统一引用 |
| 扫码即联绑定 | `src/runtime/wecom/binding.py` + `POST /wecom/bind` + `GET /wecom/bind/confirm`（公开） | 企微 OAuth getuserinfo |
| 审批卡片 | `service.build_approval_card` / `send_template_card` + `POST /wecom/push-approval` | `engine.execute/reject` + 权限③层 + 审计 |
| 审批按钮路由 | `wecom_ingest.parse_approval_event_key` + `connectors.py` 回调 → `im_bridge.process_approval` | 既有验签/解密、引擎单例 |
| 只读查询 | `im_bridge.handle_text_query`（plan 不 execute，L0–L2） | `engine.plan` + 零真名脱敏 |
| 测试 | `tests/test_wecom_im.py`（19 passed） | — |

### 9.2 关键铁律落实
1. 🔴 **租户 fail-closed**：审批前 `session.tenant_id == 绑定解析 tenant` 校验，跨租户一律拒绝；corp→tenant 解析失败返回 None。
2. 🔴 **零真名出站**：所有卡片/回执文本经 `sanitize_im_text`（长 token 优先替换防子串错洗）。
3. 🔴 **凭证铁律**：仅 `.env`（`ZHIYAN_WECOM_*`）；`status()` 与 confirm 响应零密钥泄露；未配置优雅降级。
4. **不破管**：企微未配 → 绑定/审批/查询返回明确 reason，绝不抛异常阻塞平台。

### 9.3 与评估对照的修正
- 评估 §2"缺失 inbound 半边"已证伪：验签/解密/回调端点**已存在**，缺口实为"绑定 + 卡片 + 路由 + 过滤"。
- 评估 §6.1"回调验签必须按企微协议自己实现"——现已确认既有实现即企微协议（SHA1 排序签名 + AES-256-CBC），无需重做。
- Phase C（双向多轮会话）仍按需后置，初版严格无状态（每条消息独立意图）。

### 9.4 待杜总拍板（未变）
1. Phase A 审批卡片先接哪条终审链（默认已覆盖 `approve-multi` / 单 Agent `approve`；bid_intel 终审端点如需专属卡片可再加）。
2. IM 查询是否先锁"只读 + 外圈免费"口径（当前已锁 L0–L2 只读，不 execute）。
3. 生产部署前需真实企微凭证（CorpID/Secret/AgentId + 回调 Token/AESKey）填入服务器 `.env`。

---

> 评估（§0–§8）为架构论证；§9 为 2026-08-03 落地实况：Phase A（审批）+ Phase B（只读查询）已建并测试通过，Phase C 留待后续。
