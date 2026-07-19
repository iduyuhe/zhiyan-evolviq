# 智衍 EvolvIQ · 2026-07-16 全天复盘（V1 收官 → 投运上线）

> 范围：从「V1 战略项收官」到「部署上线到云服务器」的全链路工作。
> 驱动方式：用户以极简指令逐层推进（依次完成 → 继续 → 需要 → 复盘 → 需要 → 要 → 需要 → 需要 → 把…补进草稿 → 部署 → 做一下复盘）。
> 一句话结论：**白天把 V1 四项以零架构风险闭合，傍晚补齐"可对外演示 + 可对外分发 + 可对外访问"三件套，晚上成功把最小可用栈部署上线。**

---

## 一、全天记分牌

| 维度 | 结果 |
|------|------|
| V1 战略项 | **4/4 闭合**（V1-1 ~ V1-4） |
| 单元测试 | `pytest` **48/48**（基线 31 → 净增 17） |
| 前端构建 | `vite build` **47 modules** 干净（基线 45 → +2） |
| 战略对齐矩阵 M1–M9 | **全绿** |
| 遗留 V1 挂起项 | **0**（多 Agent 协作编排为 T4 既定非目标） |
| 对外演示数据 | 10 条调参建议 / 自主率 76.1% / 介入准确率 91.7% |
| 运维看板 | 自包含 HTML，单图 900×2792 / 301KB |
| 公众号草稿 | 已入箱（media_id `F8HQL…`），未发表 |
| 云部署 | ✅ 上线 `http://demo-host:3006`，端到端验证通过 |
| 真实修复的 bug | `pyproject.toml` 漏列 `apscheduler` |

---

## 二、工作流五阶段

### 阶段一 · V1 战略项收官（上午）
四项的实证已在原 V1 收官复盘中记录，要点：
- **V1-1 Neo4j 知识图谱**：102 节点 / 95 边；driver 惰性导入 + Neo4j 不可达回退内存图。
- **V1-2 MCP 能力层联邦**：统一 server 暴露 **38 工具**（供应链 6 / pm 4 / yield 4 / 其余 8 Agent 各 3），与 T4 收敛一致、零运行时风险。
- **V1-3 工业协议网关**：Modbus/MQTT/OPC-UA/IPC-CFX 四类齐备，`ensure_ready()` 守卫化解 lifespan 坑。
- **V1-4 按效果调参**：补齐漏掉的 `yield_analysis` 第 11 个授权边界；阈值夹紧 [0.5,0.95]，只调阈值不碰业务数字。

### 阶段二 · 对外演示数据快照
- `data/seed/metrics_demo.json`：11 Agent 精算效果信号，刻意触发全部 3 类调参规则（放宽 2 / 收紧 4 / 提上限 4，ipc 无建议）。
- `src/runtime/core/demo_seed.py`：`seed_demo_data()` 注入 `metrics` + `intervention_queue` 内存单例，**仅 `ZHIYAN_DEMO_DATA=1` 由 lifespan 加载，不污染测试**。
- KG 演示数据本就来自既有 16 个 `data/seed/*.json`（102/95），无需再种。
- 验证：`verify_demo_data.py` 产出 10 建议、全局自主率 76.1%、介入准确率 91.7%。

### 阶段三 · 可截图运维看板
- `scripts/gen_demo_dashboard.py`：**调用真实引擎**（`seed_demo_data()` + `StrategyTuner.effect_signals()/suggest()`）产出快照，渲染 `docs/DEMO_DASHBOARD.html`。数据源=引擎真实计算，非手填。
- 看板自包含、零外部依赖、可离线截图；V5 杂志风（#2563eb 单色零渐变留白，@media print 可打印）。含 6 KPI 卡 + 11 Agent 信号表 + 10 调参建议清单。

### 阶段四 · 发布与分发（公众号草稿 + 配图）
- 发布走**微信公众号（工业5点0产业生态联盟）**，仅存草稿箱、不发表。
- `scripts/gen_cover_v1.py`：PIL 生成 V5 风封面（900×500，单色零渐变）。
- `scripts/build_release_draft.py`：RELEASE_NOTE_V1 适配为 V5 微信 HTML（禁用 ul/ol/li，全 p+符号），注入 4 个 URL。
- **两处铁律守住**：① 封面传两次（`permanent` 取 `thumb_media_id` + `article-img` 取正文头图 `?from=appmsg` URL，避开 `?wx_fmt` 手机端乱码）；② 文末固定顺序「参考来源 → 全链路生态图 → 招募动图 → 免责声明」。
- 看板配图：Chrome headless 截图（900×2792 / 301KB）→ `article-img` 上传 → 插入「📊 平台运行态（演示快照）」小节 → 调 `draft/update` **就地更新原草稿**（不新增重复、不发表）。
- 草稿 media_id：`F8HQLzzX8SrIMRYLwuzJb61F7f3J1l_Ufmo9uPij87fCTyUymGByGp4j0fJnk3Vv`。

### 阶段五 · 部署上线到云服务器（晚上）
- 目标 `demo-host`，用户给的 `:3004` 实为关闭端口；**SSH 实际在 22**。
- 只读勘察：OpenCloudOS 9.4 / 2vCPU / 1.9G 内存 / 50G 盘剩 8.2G；Docker 29.6.1 已运行；非空白机（已跑 a-geo/clmx/cjgc 等），**未触碰任何他人项目与 80 端口 nginx**。
- **修了真实 bug**：`pyproject.toml` 漏列 `apscheduler` → runtime 容器启动即崩、无限重启；补上后正常。
- 绕开 `infra/docker-compose.yml` 的 build context 错位，用独立最小 compose（`docker-compose.deploy.yml`，context=项目根，仅 runtime+studio，注入清华 pypi + npmmirror 镜像源）。
- **安全组坑**：8080/8000 被云 SG 丢弃；实测放行 3000 段，studio 映射到 **3006** 即外部可达。用户只访问 `:3006`，前端 `/api` 经 studio nginx 内部代理到 runtime:8000，无需 8000 对外。
- 端到端验证（从本机真实打 `:3006`）：`/`→200；`/api/strategy`→11旋钮/11信号/10建议；`/api/kg/stats`→102/95；`/api/gateways`→4/4 就绪。
- **对外演示地址：http://demo-host:3006**

---

## 三、踩坑与修复（核心资产）

| # | 阶段 | 现象 | 根因 | 修复 | 复用价值 |
|---|------|------|------|------|----------|
| 1 | V1-1 | `neo4j_client` SyntaxError | `from=` 保留字 + `%` 拼接 | 参数化 `parameters=` + 关系类型白名单常量 | Neo4j 写必须参数化 |
| 2 | V1-3 | 网关 `ready=0`、读数空 | `httpx.ASGITransport` 不触发 FastAPI lifespan | `ensure_ready()` 幂等首调自初始化守卫 | **全局复用模式** |
| 3 | V1-3 | `IpcCfxGateway` TypeError | ABC 缺 `write` 抽象方法 | 补 `write`=发布事件 | ABC 子类必须实现全部抽象 |
| 4 | V1-4 | 授权边界 10/11 | `_seed_defaults` 漏 `yield_analysis` | 补 `ab-yield-default` | 新增 Agent 必同步补边界 |
| 5 | V1-4 | PydanticDeprecated 告警 | `cur.model_fields` 实例级弃用 | 改 `AuthBoundary.model_fields` 类级 | V2.11 兼容写法 |
| 6 | 数据 | `demo_seed.py` 路径错位 | 在 `src/runtime/core/`，`dirname×3` 落 `src/data/seed` | 改 `dirname×4` 到项目根 | 种子路径统一用项目根 |
| 7 | 公众号 | 正文头图手机端乱码 | 用 `material/add_material` 的 `?wx_fmt` URL | 封面传两次，`article-img` `?from=appmsg` 作正文图 | **用户铁律，永久遵守** |
| 8 | 公众号 | `draft/update` 47001 | `articles` 是【单对象】非数组，且不接受 `show_cover_pic` | 改对象 + 去 show_cover_pic + 补 `article_type:"news"` | 已沉淀为技能 `draft-update` 子命令 |
| 9 | 看板 | 截图被截断 | Chrome 视口模式只截首屏 | `--headless=new` 全页 + 自定义裁剪底白脚本 | `render_dashboard_image.py` 可复用 |
| 10 | 看板 | `os.path.exists` 路径不识 | 原生 Python 不认 `/c/` Git Bash 风格 | 改用 `C:/...` Windows 风格 | 跨脚本通用 |
| 11 | 部署 | runtime 容器无限重启 | `pyproject.toml` 漏列 `apscheduler` | 补 `apscheduler>=3.10` 重建 | **真实 bug，须回归测试** |
| 12 | 部署 | 8080/8000 外部超时 | 腾讯云安全组未放行 | 实测放行 3000 段，studio 映射 3006 | 上线前先探开放端口 |
| 13 | 部署 | compose build 拷不到 src | `infra/docker-compose.yml` context 指向 `infra/` | 独立 compose context=项目根 | 部署 compose 自管 |

---

## 四、沉淀的复用模式

1. **韧性降级铁律**：所有外部依赖（PG / Neo4j / OPC-UA / AMQP / MCP）均惰性 import + 不可达回退本地替代（SQLite / 内存图 / simulated），绝不破管、绝不阻断启动。部署上线再次验证其价值——未依赖 postgres/neo4j 也完整跑通。
2. **`ensure_ready()` 幂等守卫**：需 lifespan 初始化的组件，API handler 内首调自初始化，兼容 `ASGITransport` 不触发 lifespan。
3. **事实锚点铁律**：调参/优化只改策略阈值 / 实体关系，绝不改写业务数字或动作。演示数据 / 看板 / 发布文案均标注"演示快照、非生产真实业务数字"。
4. **公众号发布铁律**（用户定制）：V5 杂志风（单色 #2563eb、零渐变、禁用列表标签）；正文头图双保险（article-img URL）；文末固定顺序（参考来源→生态图→招募动图→免责声明）；作者杜玉河；公众号名「工业5点0产业生态联盟」（是「点」非「.」）；默认仅存草稿箱。
5. **`draft/update` 差异**：articles 是单对象、不支持 show_cover_pic —— 已固化进 `wechat_upload.py` 的 `draft-update` 子命令。
6. **部署前端口探测**：连服务器前先 TCP 探多端口，确认 SSH 真实端口 + 安全组放行区间，避免盲连被挡（本次 3004 关、22 开、3006 放行）。
7. **部署镜像源注入**：Dockerfile 加带官方源默认值的可选 build arg（`PIP_INDEX_URL`/`NPM_REGISTRY`），部署时覆盖为国内镜像，不影响其他环境。

---

## 五、诚实反思（可改进点）

- **计数靠记忆翻车**：联邦工具数曾误记 40，实 38；KG 字段名（`node_count` vs `total_nodes`）一度取错导致误判 None。教训：跨 Agent 计数 / API 字段名必须实测，不靠脑补。
- **发布前先探端口再动手**：用户给的 `:3004` 是关闭端口，若先盲连 SSH 会卡住。本次顺序（先只读 TCP 探 + SSH 诊断）正确，应成为部署前置标准动作。
- **依赖清单要回归**：`apscheduler` 漏列导致容器崩，本地 `.venv` 有而构建无。教训：新增 import 必须同步 `pyproject.toml`，CI/构建前跑一次"干净环境 import 全量"。
- **compose context 错位**：`infra/docker-compose.yml` 的 context 指向 `infra/` 与 Dockerfile 的 `COPY src/` 冲突，属既有技术债。本次用独立 deploy compose 绕开，但根因未改——后续应修 `infra/` 的 context 或 Dockerfile，避免后人再踩。
- **极简指令的推断成本**：今日多步靠极简指令推进，范围推断量大。有歧义的大项（如"全 11 Agent 联邦""部署到服务器"）用 AskUserQuestion 先行澄清，整体未跑偏。

---

## 六、剩余项与下一步

- **唯一未做 V1 项**：多 Agent 协作/编排 —— T4 既定非目标，建议保持不纳入范围。
- **发布节奏**：草稿已在公众号箱，等用户审核后说"发表"再推送。
- **部署可选增强**（用户未要求，待定）：
  1. `infra/docker-compose.yml` 的 context 错位根因修复（避免后人踩）；
  2. 把 postgres/neo4j 也拉起跑完整栈（演示目前用降级模式）；
  3. 加 nginx 反代让演示走 80/域名；
  4. 若需直接 API 访问，再开安全组 8000。

---

*全天复盘结论：V1 四项零架构风险闭合 + 演示/分发/部署三件套齐备，对外演示地址 http://demo-host:3006 端到端可访问。所有复用模式已提升至 MEMORY.md，微信发布差异已固化进技能，工作逐项目归档至 .workbuddy/memory/2026-07-16.md。*
