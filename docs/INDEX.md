# 智衍 EvolvIQ · 文档地图（docs/INDEX.md）

> **权威声明**：`MASTER_EXECUTION_PLAN.md` 是本仓库**唯一执行总纲**（v1.4，已覆盖至 v31 S3 收口）。任何与其他文档冲突处，以 MASTER 为准。本 INDEX 仅为导航，不改变文件内容。
>
> **铁原则**：Tier 1／Tier 2 文档中每句结论必须锚定 `tests/`（pytest 数字）或生产 E2E 实测；无法锚定的须标「假设待验证」。本仓库此前存在「分析重、验证轻」失衡——收口即治理此失衡。
>
> **制定**：2026-07-29 战略盘点。状态标记：✅=与 v31 实测一致 ｜ ⚠️=部分滞后/需追平 ｜ 🗄️=归档快照(历史/假设待验证) ｜ 🆕=待建。

---

## Tier 1 · 权威活文档（人读入口，随产品更新）

| 文件 | 主题 | 状态 | 备注 |
|---|---|---|---|
| `MASTER_EXECUTION_PLAN.md` | 唯一执行总纲（S1/S2/S3 全收口） | ✅ | 每阶段有 commit+测试数+一页汇报背书 |
| `S2_STAGE_REPORT.md` | S2 阶段真相（344 passed） | ✅ | 三件套验收证据 |
| `S3_STAGE_REPORT.md` | S3 阶段真相（419 passed，净增 75） | ✅ | 六层交付对照表 |
| `ENVIRONMENT_PERCEPTION_PLAN.md` | ⑥环境感知细案（α/β/γ 三阶段） | ✅ | MASTER §3.7 引用 |
| `SOCIAL_CHANNEL_SETUP.md` | P2 社交通道细案 | ✅ | 等杜总企微密钥解锁 |
| `FIRST_CUSTOMER_PILOT.md` | P3 首客试点细案 | ✅ | 等杜总选场景+企业 |
| `PRICING_MODEL.md` | 定价与信任爬梯模型（对外可公布） | 🆕 | **待杜总定调免费额度/付费线默认值** |

---

## Tier 2 · 对外参考（冻结版，对外可讲，按需更新）

| 文件 | 主题 | 状态 | 备注 |
|---|---|---|---|
| `WHITEPAPER.md` | 对外叙事白皮书 | ⚠️ | 须与 v31 实测对齐、删虚 |
| `TECHNICAL_WHITEPAPER.md` | 技术白皮书 | ⚠️ | 同上 |
| `RISK_GOVERNANCE_WHITEPAPER.md` / `.zh` | 风险治理白皮书 | ✅ | 红线与 MASTER 一致 |
| `HOLOGRAPHIC_INFO_SOURCE_ARCHITECTURE.md` | 全息真相源架构 | ✅ | 三主义活循环 |
| `OPEN_SOURCE_COMPETITIVENESS_MAP.md` | 开源竞争力地图（竞品合索引） | ✅ | 建议作为竞品唯一切入点 |
| `COMPETITIVE_EVALUATION_SIEMENS.md` | 竞品-西门子评估（子文档） | 🗄️ | 合并入上者 |
| `COMPETITIVE_EVALUATION_MIDEA.md` | 竞品-美的评估（子文档） | 🗄️ | 合并入上者 |
| `COMPETITIVENESS_MATURITY_SYNTHESIS.md` | 竞争力成熟度综合 | 🗄️ | 结论已沉淀 MASTER |
| `PRODUCT_LANDING_PLAN.md` | 落地页计划 | ⚠️ | 待 S2 免费版界面定稿 |
| `LAUNCH_ANNOUNCEMENT.md` | 发布公告 | ⚠️ | 须对齐 v31 对外口径 |
| `ECOSYSTEM_LAUNCH.md` | 生态发布 | ⚠️ | 引力 N≈0，叙事需克制 |
| `DATASHEET.md` | 数据表 | ⚠️ | 数字须追 v31 |
| `GUIDE.md` / `GUIDE.zh.md` | 使用指南 | ✅ | |
| `ENTERPRISE_GUIDE.zh.md` | 企业指南 | ✅ | |
| `DOMAIN_GUIDE.md` | 领域指南 | ✅ | |
| `TUTORIAL.md` | 教程 | ✅ | |
| `API_AUTH.md` | API 鉴权 | ✅ | |
| `INTEGRATION.md` | 集成 | ✅ | |
| `DEPLOYMENT_GUIDE.md` | 部署指南 | ✅ | 双入口架构已生产验证 |
| `MULTI_AGENT_ORCHESTRATION.md` | 多智能体编排 | ✅ | |
| `MEMORY_AND_LEARNING.md` | 记忆与学习 | ✅ | |
| `VALUES_AND_METHODOLOGY.md` | 价值观与方法论 | ✅ | |
| `MATURITY_MODEL.md` | 成熟度模型 | 🗄️ | 设计期假设，待生产验证 |

---

## Tier 3 · 归档快照（历史/假设待验证，冻结不改）

> 以下文档多为 2026-07-27 定调「讨论期」产物，结论已沉淀进 MASTER 或代码。保留供追溯，不对外引用为权威。

| 文件 | 主题 | 状态 | 备注 |
|---|---|---|---|
| `STRATEGY_SYSTEM_ROADMAP.md` | 旧战略路线图 | 🗄️ | **滞后 v23，与 MASTER 冲突→降级历史背景** |
| `PRODUCT_DEVELOPMENT_PLAN.md` | 旧产品开发计划 | 🗄️ | **滞后 v23→降级历史背景** |
| `NEXT_STEPS_DISCUSSION.md` | 讨论存档 | 🗄️ | MASTER 已声明其使命完成 |
| `ALIGNMENT_REPORT.md` | 对齐报告 | 🗄️ | 结论已沉淀 |
| `GLOBAL_ALIGNMENT_REPORT.md` | 全局对齐报告 | 🗄️ | 同上 |
| `GAP_REVIEW_v29.md` | v29 缺口回顾 | 🗄️ | 已收口 |
| `PRACTICALITY_ASSESSMENT.md` | 实用性评估 | 🗄️ | 讨论期假设 |
| `PREREQUISITES_ASSESSMENT.md` | 准备度评估 | 🗄️ | 讨论期假设 |
| `DEPLOYMENT_READINESS.md` | 部署准备度 | 🗄️ | 部分已生产验证 |
| `DEPLOYMENT_GAP_ACTION.md` | 部署缺口行动 | 🗄️ | 多数已闭环 |
| `INTEGRATION_CAPABILITY_ASSESSMENT.md` | 集成能力评估 | 🗄️ | 讨论期 |
| `SMIC_DEMO.md` | 中芯 demo | 🗄️ | 历史 demo |
| `SMIC_ALIGNMENT.md` | 中芯对齐 | 🗄️ | 历史 |
| `SMIC_FUNCTIONAL_ALIGNMENT.md` | 中芯功能对齐 | 🗄️ | 历史 |
| `SMIC_FUNCTION_MAP.md` | 中芯功能映射 | 🗄️ | 历史 |
| `RELEASE_NOTE_V1.md` | v1 发布说明 | 🗄️ | 历史 |
| `RETROSPECTIVE_2026-07-16.md` | 回顾 | 🗄️ | 历史 |
| `SUMMARY_20260724.md` | 小结 | 🗄️ | 历史 |
| `TEST_REPORT.md` | 测试报告 | 🗄️ | 可并入 S2/S3 汇报 |
| `LECTURE_FRAMEWORK.md` | 演讲框架 | 🗄️ | 对外素材 |
| `LECTURE_COSCO.md` | 中远海运演讲 | 🗄️ | 对外素材 |
| `STRATEGIC_CONSOLIDATION.md` | 战略整合 | 🗄️ | 讨论期，部分已沉淀 MASTER |

---

## 收口待办（按你确认力度：先出地图，不删不改）

1. ✅ 本 INDEX 建立，MASTER 明定为唯一权威源。
2. ⏭️ **追平两篇滞后总纲**（你定）：把 `STRATEGY_SYSTEM_ROADMAP` / `PRODUCT_DEVELOPMENT_PLAN` 补到 v31，或直接在其顶部加「已并入 MASTER，本文件仅作 v23 前历史背景」声明。
3. ⏭️ **竞品合并**：`OPEN_SOURCE_COMPETITIVENESS_MAP` 作唯一索引，两篇 `_SIEMENS/_MIDEA` 标注为子文档。
4. ⏭️ **定价白皮书**：`PRICING_MODEL.md` 待你确认免费额度/付费线默认值后起草。
5. ⏭️ **对外叙事对齐**：`WHITEPAPER` / `LAUNCH_ANNOUNCEMENT` / `ECOSYSTEM_LAUNCH` 的数字与口径须与 v31 实测一致（引力 N≈0 处叙事需克制）。

*本文件为导航地图，不替代任何文档内容。任何内容修订请走对应 Tier 1 文档并 git 留痕。*
