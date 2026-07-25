# EvolvIQ Open-Source Launch Announcement

> Bilingual launch copy for promoting the open-sourcing of EvolvIQ.
> English version targets Hacker News / Dev.to; Chinese version targets the
> WeChat official account **工业5点0产业生态联盟** (operator: 杜玉河).

---

## 🇬🇧 English — Hacker News / Dev.to

### Hacker News (Show HN)

**Title:**
```
Show HN: EvolvIQ – an open-source AI-native platform with 20 industrial agents for electronics manufacturing
```

**Text:**
```
EvolvIQ (智衍) is an AI-native platform for electronics / semiconductor
manufacturing that ships 20 domain Agents out of the box — supply chain
kitting, OEE optimization, yield analysis, SPC, energy/carbon, cost, S&OP,
procurement, and an executive cockpit.

What makes it different from "yet another LLM wrapper":

- Agents are the product. Each agent is a deterministic, auditable module
  (BaseAgent.analyze(goal) -> dict). Metrics are computed from seed/real data,
  not LLM guesses — so ROI deltas are reproducible.
- Resilience by design. If PostgreSQL / Neo4j / an industrial gateway is
  unreachable, it degrades gracefully (SQLite, in-memory graph, simulated
  protocols). The system never hard-crashes on a missing dependency.
- Authorization guardrails. Every agent has an AuthBoundary (confidence
  threshold, max daily autonomous actions, require-approval actions). Humans
  stay in the loop for risky moves.
- Standard protocols. 4 gateways: OPC-UA, Modbus, MQTT, IPC-CFX. MCP federation
  exposes 65+ tools over HTTP / stdio.
- Apache-2.0, fully open. 20 agents + platform runtime + Studio UI.

We just pushed v20 to GitHub. Looking for feedback from folks who've built
manufacturing / MES / industrial-IoT systems.

Repo: https://github.com/iduyuhe/zhiyan-evolviq
```

### Dev.to Article Outline

**Title:** "We open-sourced 20 industrial AI agents — here's what we learned
building an AI-native manufacturing platform"

1. **Why "Agent as a product"** — the shift from dashboards to autonomous
   domain agents; deterministic fact anchors.
2. **Architecture in 5 layers** — Studio → Governance (router/auth) →
   Intelligence (agents) → Capability (MCP federation + 4 gateways) →
   Connect (OPC-UA/Modbus/MQTT/IPC-CFX).
3. **The resilience rule** — every external dependency has a fallback; show the
   PostgreSQL→SQLite and Neo4j→in-memory examples.
4. **Guardrails, not autopilot** — AuthBoundary model and the "human-in-the-loop
   for risky actions" principle.
5. **A real run** — supply-chain kitting 41.7% → 100%; energy/carbon 4 retrofit
   opportunities with payback periods.
6. **How to contribute** — the TUTORIAL.md path to add your own agent.
7. **What's next** — roadmap (multi-agent orchestration, i18n, live data
   adapters).

---

## 🇨🇳 中文 — 微信公众号（工业5点0产业生态联盟）

> 作者：杜玉河 ｜ 公众号：工业5点0产业生态联盟
> 发布时按排版铁律插入封面图、生态 banner、招募动图、参考来源与免责声明。

### 标题备选
1. 我们开源了 20 个工业智能体：一个 AI 原生的智能制造操作系统
2. 智衍 EvolvIQ 开源：20 个 Agent 如何把车间变成"会思考的工厂"
3. 从仪表盘到自主智能体：我们为什么把工业 5.0 做成了开源平台

### 正文（约 1200 字）

今天，我们正式把**智衍 EvolvIQ**开源了。

这不是又一个"套壳大模型"的演示。它是一个**AI 原生的工业智能体开发与部署平台**，开箱即带 **20 个制造领域智能体**——从供应链齐套、OEE 优化、良率分析，到能源碳排、制造成本、产销协同，再到经营驾驶舱。

**为什么是"智能体即产品"？**

传统 MES/低代码平台给你仪表盘，数据要人看、决策要人做。EvolvIQ 反过来：
每个智能体是一个**确定性、可审计的模块**——输入一句话目标，输出量化结果和
可追溯的行动清单。关键数字是种子数据或真实数据算出来的，不是大模型"编"的，
所以每一次 ROI 提升都可复现。

我们做过一次真实推演：供应链智能体把某 BOM 的**齐套率从 41.7% 拉到 100%**，
缺料风险项从 6 降到 0，交期准时率从 75% 提到 91.7%；能源碳智能体识别出 4 项
降碳机会，并算出了每一项的投资额和回收期（比如空压机改造回收期 1.8 年）。

**最硬的一件事：韧性降级**

工业现场最怕"依赖一挂，系统就瘫"。EvolvIQ 的设计铁律是：**任何外部依赖不可达，
自动回退到本地替代**——PostgreSQL 挂了用 SQLite，Neo4j 挂了用内存图，工业网关
挂了走模拟协议。系统永不崩。这意味着你哪怕零数据、零真实源，也能先把能力演示跑起来。

**授权护栏，而不是自动驾驶**

20 个智能体各有独立的授权边界：置信度阈值、每日自主行动上限、需人审批的动作
类型。风险动作（如自动采购、停产）一律交回人决策。人始终在环。

**标准协议，接得进真实工厂**

平台内置四类工业协议网关——OPC-UA、Modbus、MQTT、IPC-CFX。现代 PLC/SCADA
原生提供这些接口；MCP 联邦对外暴露 65+ 工具。换句话说，**不存在"产品接不进"
的问题，真正的工程量在节点和字段的映射**。

**完全开源，Apache-2.0**

平台基座 + 全部 20 个智能体，一次性开源。我们选 Apache-2.0，因为它对社区和企业
都友好，含专利条款。差异化靠托管服务、数据和行业版，不靠闭源智能体。

我们写了一份**应用白皮书**和**技术白皮书**，还有一份手把手的**智能体开发教程**——
照着做，你也能给平台贡献一个新的工业智能体。

工业 5.0 不是把人换成机器，而是让机器承担重复判断，让人专注创造。EvolvIQ 是我们
朝这个方向迈出的一步。欢迎来 GitHub 提 Issue、发 PR，一起把工业智能体生态做厚。

### 文末固定模块（发布时按铁律插入，非本文案正文）
- 参考来源：EvolvIQ GitHub 仓库、平台白皮书与实测报告（内部）
- 全链路闭环生态 banner 图
- 招募事业城市合伙人 / 培训合作伙伴动图
- 免责声明

---

## Assets & links

- Repository: https://github.com/iduyuhe/zhiyan-evolviq
- README (EN): `README.md` ｜ README (中文): `README.zh.md`
- Application whitepaper: `docs/WHITEPAPER.md`
- Technical whitepaper: `docs/TECHNICAL_WHITEPAPER.md`
- Agent dev tutorial: `docs/TUTORIAL.md`
- Roadmap: `ROADMAP.md` ｜ Security: `SECURITY.md` ｜ Changelog: `CHANGELOG.md`
