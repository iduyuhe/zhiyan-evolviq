# 生态飞轮启动方案（阶段 6.1 · 攻击战略头号缺口 N=0）

> 配套：`PRODUCT_DEVELOPMENT_PLAN.md` §2.1 / `ROADMAP.md` Near-term / `GAP_REVIEW_v29.md` 缺口 B
> 一句话：技术引擎已 207 passed 就绪，但**生态网络引力 N=0**——战略 §2.3.2 说"天花板能否兑现全系于此"。本文件把"六柱飞轮"翻译成今天就能执行的动作。

---

## 0. 为什么这是第一杠杆

| 事实 | 含义 |
|---|---|
| CCI 公式 `CCI = M × (α·S + β·A + γ·N)`，恒有 `CCI ≤ M` | 成熟度 M 是闸门，但**网络引力 N 是乘数里我们唯一能主动拉满的项** |
| 智衍 `A=1.00`（Apache 全开源）已顶满 | Z 轴自主可控已就位，剩下全看 N |
| 巨头 `N` 靠资金/数据飞轮，我们靠**开放网络正反馈** | 不拼钱，拼"开发者/集成商愿不愿意来" |
| 现状：代码已开源（GitHub public），**零运营** | N≈0，CCI 天花板（0.657）兑现不了 |

**结论**：不启动飞轮，再多功能也只是"自嗨仓库"。阶段 6.1 是技术闭环→生态闭环的开关。

---

## 1. 六柱飞轮 → 具体动作映射

| 飞轮柱 | 本轮可落动作 | 产出物 |
|---|---|---|
| **P1 生态引力** | GitHub Discussions 开张 + Good First Issue 池 + 贡献入口 | 社区有了"入口" |
| **P3 协同进化** | "贡献你的 Agent / 本体"模板 + 审批门(workflow) | 社区共建机制 |
| **P4 标准话语** | 抛"工业智能体开放标准"叙事帖 + 公开本体 schema | 占据话语位 |
| **P2 信任主权** | 强调 Apache-2.0 + 不碰账本定位 | 反 retrofit 锁定软肋 |
| **P5 人才磁场** | 贡献者署名 + 案例展示 | 反哺 P1 |
| **P6 共识飞轮** |  monthly 进展公开 + 路线图共治 | 放大引力 |

---

## 2. GitHub Discussions 种子议题（直接可发）

1. **【共治】智衍工业智能体开放标准：我们应该先标准化哪一层？**（网关契约 / 本体 schema / 事件总线 UNS / 回写审计桥）—— 引标准话语。
2. **【晒场】你用智衍接了什么设备 / 什么 ERP？** —— 收集真实场景，feed 进首客。
3. **【求助】我想贡献一个 Agent，从哪上手？** —— 引向贡献指南 + Good First Issue。
4. **【理念】为什么"图谱≠真相源"，三主义活循环才是** —— 对外讲差异化，反 Palantir 静态符号。
5. **【路线】v29.8 之后我们该先攻生态还是先攻首客？** —— 让社区参与路线图。

---

## 3. Good First Issue 池（源自代码真实缺口，可直接贴）

> 每条含：标题 / 难度 / 落点文件 / 验收。优先级按"既能帮社区上手、又能补我们缺口"。

1. **[good-first-issue] 数据源配置 UI 连通性验证**（中）
   - 落点：`studio/src` 数据源配置面板 + `src/runtime/data_sources/*`
   - 验收：保存前发一次 test 连接，成功才允许保存；失败显式报错（落实路线图 §4.4 铁律）。
2. **[good-first-issue] 企微/钉钉 隐性信号接入连接器**（中）
   - 落点：新增 `src/runtime/connectors/wecom_ingest.py` + `tacit_capture.py` 路由
   - 验收：收到企微 webhook → 经 token 校验 → 入 UNS `social` 路 → 抽取即锚定；单测覆盖 token 拒绝。
3. **[good-first-issue] 邮件渠道隐性捕获连接器**（易）
   - 落点：`src/runtime/connectors/email_ingest.py`
   - 验收：IMAP 拉取 → 解析业务事件 → 入 `social` 路；含敏感内容走审批门。
4. **[good-first-issue] 监控指标 Prometheus exporter**（中）
   - 落点：`src/runtime/monitoring.py` 暴露 `/metrics`
   - 验收：回写积压 / 网关断流 / 登录暴破 三类指标可被 Prometheus 抓。
5. **[good-first-issue] 基于 supply_chain 模板写"如何新增一个 Agent"教程**（易，文档）
   - 落点：`docs/` 新增 `AGENT_DEV_TUTORIAL.md`
   - 验收：跟着做能新注册一个可路由、可鉴权、可自进化的 Agent。
6. **[good-first-issue] 路由精度增强：消解近义目标**（中）
   - 落点：`src/runtime/engine.py` ROUTING_RULES
   - 验收：`demand_order` 与 `aps_scheduler`、`wms_logistics` 与 `supply_chain` 不再误截获（加断言测试）。
7. **[good-first-issue] 前端英文 i18n**（中）
   - 落点：`studio/src/i18n/`
   - 验收：切换中/英，全部面板文案覆盖。
8. **[good-first-issue] demo 走查视频脚本 + GIF**（易，文档/素材）
   - 落点：`docs/DEMO_DASHBOARD.html` + `screenshots/`
   - 验收：30s 内讲清"不砸 ERP 获实时决策脑"。
9. **[help-wanted] "贡献你的 Agent"脚手架**（中）
   - 落点：新增 `agents/_template/` + `CONTRIBUTING.md` 增补章节
   - 验收：`cp -r _template my_agent` 改几处即可注册进联邦。
10. **[help-wanted] 本体扩展提议工作流文档**（中）
    - 落点：`docs/ONTOLOGY_CONTRIB.md`
    - 验收：社区提本体扩展 → 走 `proposed→approve` 审批门的可操作说明。

---

## 4. 贡献入口（CONTRIBUTING.md 已存在，补两节）

在现有 `CONTRIBUTING.md` 增加：
- **Bring-your-own-Agent**：指向 `agents/_template/`，说明注册点（router / engine / federation / authorization 四处）。
- **Bring-your-own-Ontology**：指向 `OntologyStore` + 审批门，说明 `proposed→approve` 流程。
- **签名即从业（DCO）/ CLA 轻量**：一人公司，先 DCO（Signed-off-by）即可，不强制 CLA。

---

## 5. 开放标准叙事话术（对外讲，不向下看齐）

- "智衍不抄 Palantir 的 Ontology——Palantir 是**纯静态符号主义（三主义的 1/3）**；智衍是**三主义（符号/联接/经验）合一的活循环**，本体只是其中一根支柱。"
- "我们开源不是噱头，是**自主可控 Z 轴 = 1.0**：客户脱绑巨头 retrofit 锁定。"
- "真相源不是某一层，是**循环**——图谱只是某一时刻的可审计快照。"
- 目标：让社区先在我们的 UNS 事件 schema / 本体 schema / 回写审计桥 上形成事实标准。

---

## 6. 验收（本轮生态启动是否算"转起来"）

- [ ] GitHub Discussions 开张，≥3 个种子议题发出
- [ ] Good First Issue 池 ≥10 条进 GitHub Issues 并打 label
- [ ] `CONTRIBUTING.md` 增补"贡献 Agent / 本体"两节
- [ ] 至少 1 篇开放标准叙事对外发布（公众号 / Discussions）
- [ ] 30 天内产生 ≥1 个外部贡献者 PR（飞轮自转的硬指标）

*本方案是"启动"，不是"做完"。飞轮一旦有外部 PR 自转，N 开始爬升，CCI 天花板才有意义。*
