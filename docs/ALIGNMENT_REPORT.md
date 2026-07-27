# 智衍 EvolvIQ · 三合一战略/功能/代码审计报告

> 审计时间：2026-07-28　|　代码基线：commit `461ebec`（v30.0 α，242 passed）
> 方法：战略·功能·性能·代码 四段，全部以 **grep/行号/测试输出/基准数据** 为证据，不采信文档自述。
> 配套数据：`bench_result.json`、`scripts/_deploy/bench_align.py`、`scripts/_deploy/smoke_check.py`

---

## 0. 执行概要（结论先行）

| 维度 | 结论 | 一句话 |
|---|---|---|
| **战略对齐** | 🟢 地基扎实，主线在轨 | 六路感知/三主义闭环/网关/UNS/隐性捕获/蓝弧/自进化/环境感知⑥ 全部落地代码；S1 已完成 |
| **功能对齐** | 🟢 全绿 | 全量 pytest **242 passed / 0 failed**；2 个良性 teardown 警告 |
| **性能对齐** | 🟢 单用户极快，并发受单事件循环约束 | 单线程 p99 < 2.1ms，bootstrap 4.7ms；进程内并发 p95 60–80ms（TestClient 串行化，**非生产真实瓶颈**） |
| **代码健壮性** | 🟢 P0 与隔离主干已修（当日闭环） | ✅ 匿名降 viewer + 多租户隔离强制（写回/KG/会话）+ 4 项对抗测试入门禁；余 5 项 P1 见 §4.2 |
| **生产健康** | 🟢 白屏红线守住 | 生产 `https://zhiyan.weomnitech.com.cn` 冒烟门禁 **PASS（无白屏）** |

**核心判断**：系统"地基"（战略架构 + 功能完整性）已经很强，可以继续向下推进 S2。但**多租户隔离与鉴权边界是 S2 对外前的硬阻断项**，必须在本阶段收口，否则一旦外部租户进来就会暴露越权/串数据。

---

## 1. 战略对齐矩阵

> 对照 `STRATEGY_SYSTEM_ROADMAP.md` + `MASTER_EXECUTION_PLAN.md` 的目标清单，逐项用代码证据判定。

| # | 战略目标 | 代码证据（文件:行 / grep） | 状态 |
|---|---|---|---|
| 1 | **路线 A 原生赋能者**（不推倒 ERP，叠加决策脑+真相源） | `writeback.py` 仅做审计桥不碰账本；`main.py:234` 注释"不推倒账本" | ✅ |
| 2 | **六路感知 ①②③④⑤⑥** | `uns.py:30-36` 全 7 个 channel 枚举 + `publish_gateway/system/human/social/meeting/collab/environment` | ✅ |
| 3 | **三主义闭环（符号/连接/行为）** | 符号=`knowledge_graph.py`+审批门；行为=`consequence.py`+`blue_arc.py`+`writeback`；连接=LLM 推理 | ✅（连接面仍在扩） |
| 4 | **阶段1 网关实时流进 agent** | `gateways/`(opcua/modbus/mqtt/ipc_cfx) + `ensure_ready` + 失败回退 simulated | ✅ |
| 5 | **阶段2 轻量 UNS 统一总线** | `uns.py`(publish/subscribe/credibility) + `ROUTEABLE_CHANNELS` | ✅ |
| 6 | **阶段3 隐性捕获面（人/社交/会议/协作）** | `tacit_capture.py`+`api/tacit_capture.py`+`test_tacit_capture.py` | ✅ |
| 7 | **阶段4 信息补录蓝弧** | `blue_arc.py`+`api/blue_arc.py`+`test_blue_arc.py` | ✅（雏形闭环） |
| 8 | **阶段5 自进化成熟（P2 反思）** | `evolution.py`+`test_p2_evolution.py`+`test_p1_self_learning.py` | ✅（雏形） |
| 9 | **阶段6 环境感知第⑥路（S1 α）** | `env_perception.py`(credibility 分级门) + `env_sources/`(policy/market/benchmark 三适配器) | ✅（S1 完成，242 passed，commit `683f70c`） |
| 10 | **执行回写审计桥 / 不反向喂脑** | `api/writeback.py` 4 端点；写失败进 pending 重试，不阻断主流程 | ✅ |
| 11 | **多租户 + JWT 体系** | `authn/`(config/deps/service/roles) + `api/tenants.py` + `test_multi_tenant.py` | 🟡（隔离未强制，见 §5 P1） |
| 12 | **全局 JWT 鉴权门禁** | `main.py:210` `_AUTH_DEPS=[Depends(require_auth)]` 挂全部受保护路由 | 🟡（匿名 SUPERADMIN，见 §5 P0） |
| 13 | **监控告警三件套** | `api/monitoring.py`+`test_monitoring.py`（回写积压/网关断流/登录暴破） | ✅ |
| 14 | **通知渠道（Log/Email/WeCom）** | `notifiers.py`+`test_notifiers.py` | ✅ |
| 15 | **社交通道生产接入（企微/钉钉/邮件）** | `connectors/`(wecom/dingtalk/email)+`api/connectors.py`+`test_social_connectors.py`(9 passed) | 🟡（企微暂停，代码就绪，待密钥） |
| 16 | **抽取即锚定（grounding 铁律）** | `env_perception.py:163-167` official→KG draft+经验库+预期后果 | ✅ |
| 17 | **人工审批护栏（_needs_review）** | `env_perception.py:165` 非 official 一律进 `_needs_review` | ✅ |
| 18 | **S2 无感转型 / 三圈解锁 / 共生环** | 计划中，未开工（下一主线阶段） | 🔴（计划中） |

**战略结论**：地基层（阶段 0–6 的核心引擎）全部以真实代码落地，路线图从"纸面"走到了"可运行"。唯一未开工的是 S2 商业包装层——这正是下一阶段，且 S2 的功能缺口（多租户隔离、SaaS 计费、G5 透明标注）恰好与 §5 的代码 P1 重叠，**修代码 = 推进 S2**，不冲突。

---

## 2. 功能对齐（测试卫生 + 隐藏缺陷逼出）

### 2.1 全量测试结果
```
命令：.venv/Scripts/python.exe -m pytest tests/ -q
结果：242 passed, 2 warnings in 76.01s  (0 failed)
```
- 33 个测试文件、覆盖：authn / blue_arc / consequence / data_sources / env_perception / field_mapping / memory_p0 / monitoring / multi_tenant / notifiers / orchestrator / p1_self_learning / p2_evolution / pm / quality_trace / rag_approval / supply_chain / tacit_capture / twin_reasoning / uns / writeback / social_connectors / yield 等。
- **2 个 warning**：`aiosqlite` "Event loop is closed"（仅测试 teardown 阶段，由 `test_social_connectors` 的后台线程在循环关闭后写回触发），**非业务失败**，但提示测试 teardown 未正确 await 后台任务。

### 2.2 生产冒烟（白屏红线）
```
scripts/_deploy/smoke_check.py https://zhiyan.weomnitech.com.cn
→ [PASS] 冒烟门禁通过：前端不会白屏
```

### 2.3 测试卫生缺口（建议）
- ⚠️ `test_social_connectors` 的后台线程未优雅 join，导致 aiosqlite 在事件循环关闭后抛 RuntimeError（被 pytest 捕获为 warning，不影响判定，但污染输出、掩盖真实 teardown 问题）。建议：测试 fixture 中 `await` 后台任务或 `thread.join()` 后再退出。

### 2.4 本次逼出的残留风险（非测试失败，是代码审计发现）
测试全绿，但**测试在 `REQUIRE_AUTH=False` 下运行**（匿名 SUPERADMIN 被当作合法），因此下列越权/隔离缺陷未被测试覆盖——它们只在生产强制模式下才暴露。详见 §5。

---

## 3. 性能对齐（基准）

> `bench_align.py`：进程内 `TestClient` + 真并发线程。数据落地 `bench_result.json`。

| 指标 | 实测 | SLO 建议 | 判定 |
|---|---|---|---|
| **冷启动 bootstrap**（lifespan 启动+种子加载） | **4.7 ms** | < 3s | ✅ MET |
| **单线程延迟 p99**（/health /supply-chain /kg /twin /sessions） | **< 2.1 ms**（/kg 偶发 11.55ms 尖刺） | < 50ms | ✅ MET |
| **读并发 p95**（50 线程 × 20 = 1000 请求） | /health 61ms，/supply-chain 80ms | < 200ms | ✅ MET* |
| **写并发**（20 线程 × 10 = 200 写 /tacit-capture/human） | **200 ok / 0 fail**，p95 48ms | 0 丢失 | ✅ MET |

**关键说明（caveat）**：
- 进程内 `TestClient` 经**单一 anyio 事件循环门户**串行化并发请求，故读/写并发 p95 的 50–80ms 主要反映"单循环串行排队"，**不是生产真实瓶颈**。真实部署用 uvicorn 异步 worker + 多进程，并发度更高。
- 单线程 p99 < 2.1ms 说明**应用自身开销极低**，瓶颈不在代码而在 I/O/外部依赖。
- `/kg` 偶发 11.55ms 尖刺：疑似首次访问触发图库 lazy 初始化或 GC，建议预热。

**性能结论**：系统轻量、响应极快，完全满足 SME 级"轻量可负担"战略定位。无需为性能做架构调整；S2 引入 PG + 连接池后并发将进一步释放（当前 SQLite/内存在真多租户写入下才是瓶颈，见 §5 P1）。

---

## 4. 代码健壮性审计（重点）

### 4.1 已做扎实的部分（正面证据）
- **网关韧性降级**：`gateways/{opcua,modbus,mqtt,ipc_cfx}/gateway.py` 均 `connect()` 先试真连、失败置 `self._mode="simulated"`，且 `manager.py:81` 后台周期重试升级 live。**绝不阻断启动**。✅
- **环境源韧性降级**：`env_sources/base.py:66-68` live 抓取异常静默回退 simulated 样本，网络 import 放函数内。**韧性铁律落地**。✅
- **前端三层白屏防御**：`ErrorBoundary.tsx` + `runtimeGuard.ts`（动态 chunk 失败自动整页重载一次）+ `zhiyan-build-marker` 版本水印，均接入 `main.tsx`。✅
- **前端 .slice 防御**：16 处未保护 `.slice()`（如 `(log.session_id||'no-session').slice(...)`）已修复（commit `461ebec`）。✅
- **Docker 健康检查无 bashism**：`docker-compose.prod.yml:84,98` 用 `pg_isready` / `wget`，规避 `cat </dev/tcp` 全假 unhealthy 陷阱。✅
- **抽取即锚定 + 审批门**：环境信号 official 直接锚定、非 official 进 `_needs_review`，符合战略三条纪律。✅

### 4.2 必须收口的问题（P0 / P1）— **审计当日已修复主干**

> **修复状态（2026-07-27，全量回归 246 passed 零回归）**：以下 ✅ 项已在审计同日落地修复，对抗测试 `tests/test_tenant_isolation.py`（4 项）已纳入零回归门禁。

#### ✅ P0 已修复 — 匿名 SUPERADMIN 越权面
- **原问题**：`src/runtime/authn/deps.py`（`require_auth` 在 `REQUIRE_AUTH=False` 时返回 `role:"SUPERADMIN"`），任何未设 `ZHIYAN_AUTH_REQUIRE=1` 的部署即开放匿名超管。
- **修复**：匿名上下文 `role` 降为 `"viewer"`（rank 0，最小权限）；管理端点（如 `/authn/users`）须 `require_role` 高权限，匿名访问返回 401/403。测试 `test_anonymous_cannot_admin_p0` 守护。

#### ✅ P1 已修复 — 多租户隔离强制化（写回 / KG / 会话）
- **根因修复**：新建 `src/runtime/context.py` 作为租户上下文单一真相源（`contextvars.ContextVar`）；`require_auth` 两分支均 `set_current_tenant(...)`；`federation.py` 删除本地重复 ContextVar 改引 context.py。
- **越权写**：`api/writeback.py` `submit_writeback` 改用 `get_current_tenant()`，**忽略请求体 tenant_id**（字段标注已废弃）。测试 `test_writeback_ignores_client_tenant_p1` 守护。
- **越权读**：`/pending`、`/stats`、`/demo-records` 均按 `get_current_tenant()` 过滤（`data_sources/writeback.py` 的 `pending()`/`stats()` 加 tenant 参数）。测试 `test_writeback_pending_isolation_p1` 守护。
- **KG 越权**：`api/knowledge_graph.py` 新增 `_effective_tenant()`——非 SUPERADMIN 忽略客户端 tenant 参数；`/query`、`/recall` 挂 `Depends(require_auth)`。测试 `test_kg_query_ignores_spoofed_tenant_p0_p1` 守护。
- **会话越权读**：`api/sessions.py` `get_session_db` 取回后校验 `row.tenant_id != tenant → 404`（防按 session_id 跨租户读）。

#### 🟡 P1 待收口（子代理深度审计追加发现，4 项）
1. **X-Tenant-Key 在 dev 模式被直接信任**：`require_auth` 非强制分支以 `X-Tenant-Key` 头即定租户（无凭据校验）。生产靠 `ZHIYAN_AUTH_REQUIRE=1` 挡；dev/demo 环境仍可伪造租户。方向：非强制模式仅允许 `default` 租户或要求 tenant key 注册校验。
2. **tacit_capture 硬编码 `tenant_id="default"`**：`api/tacit_capture.py` 隐性捕获信号全部落入 default 租户，击穿经验库/KG 隔离——多租户下 A 的会议纪要会进入共享经验库。方向：改用 `get_current_tenant()`（社交回调无 JWT 场景按连接器绑定租户）。
3. **写回 pending 队列纯内存**：runtime 重启丢失未发送回写记录，与"ERP 执行回写+审计"定位冲突。方向：落 SQLite 持久化（与 sessions 同库）。
4. **网关 simulated 回退静默喂假数据**：OPC-UA/AMQP connect 失败自动转 simulated，Agent 无感知继续基于假数据决策。方向：降级时在 UNS system 路发告警事件 + 数据带 `source_mode:"simulated"` 标记，前端连接面板红标。

#### 🟡 P1 待收口 — UNS 内存存储无并发锁
- `uns.py` `_subscribers`/`counts` 无锁；TestClient 单循环掩盖竞态，真实 uvicorn 多线程下 publish/subscribe 并发改 dict 有 race。修复：加 `asyncio.Lock`。

### 4.3 建议项（P2，子代理深度审计合并后共 10 项，摘要）
- `CHANGELOG.md` 滞后（停在 v28.2，实际 v30.0 α）——发版同步。
- `test_social_connectors` teardown 未 join 后台线程（§2.3 warning）。
- `/kg` p99 偶发尖刺——图库 lazy 初始化预热。
- CORS `allow_origins=["*"]` + `allow_credentials=True` 组合——生产收敛为白名单域。
- jwt_secret 存在双配置源（authn/config 与 Settings）——统一单源。
- `docker-compose.prod.yml` 未显式声明 `ZHIYAN_AUTH_REQUIRE`（靠 .env 注入）——compose 内显式化防漏配。
- `_needs_review` 标记只进不出（无审批消费出口 UI 闭环）——S2 补审批面板动作。
- 企微/钉钉连接器：回调重放窗口、密钥轮换缺失——生态接入扩大前收口。
- `require_auth` 与 `get_current_user` 行为统一（匿名已降 viewer，剩余为语义统一）。
- 前端 find_error*.cjs 临时排查脚本清理出仓。

---

## 5. 综合优先行动清单

### ✅ P0（已完成，2026-07-27）
| 项 | 动作 | 验证 |
|---|---|---|
| 匿名 SUPERADMIN | ✅ 匿名 `role` 降 `viewer`（最小权限）| ✅ `test_anonymous_cannot_admin_p0` 过 |
| 生产兜底复核 | ⏳ 确认两台服务器 `.env` 均含 `ZHIYAN_AUTH_REQUIRE=1` 且 runtime 已重启 | curl 无 token 返回 401 |

### 🟡 P1（S2 开工前必收口）
| 项 | 状态 |
|---|---|
| 多租户隔离强制（写回/KG/会话）| ✅ 已修（context.py + get_current_tenant 统一）|
| 隔离对抗测试 | ✅ `test_tenant_isolation.py` 4 项入门禁 |
| tacit_capture 硬编码 default 租户 | ⏳ 待修 |
| 写回 pending 队列持久化 | ⏳ 待修 |
| 网关 simulated 降级显性告警 | ⏳ 待修 |
| X-Tenant-Key dev 模式信任 | ⏳ 待修 |
| UNS 并发安全（`asyncio.Lock`）| ⏳ 待修 |

### 🟢 P2（顺手做）
- CHANGELOG 同步至 v30.0 α
- test_social_connectors teardown join
- /kg 预热消除尖刺
- require_auth / get_current_user 行为统一

---

## 6. 附录：复现命令

```bash
# 功能：全量测试
cd E:/agent_industry/zhiyan
.venv/Scripts/python.exe -m pytest tests/ -q

# 性能：基准（结果落 bench_result.json）
.venv/Scripts/python.exe scripts/_deploy/bench_align.py

# 生产白屏门禁
.venv/Scripts/python.exe scripts/_deploy/smoke_check.py https://zhiyan.weomnitech.com.cn

# 战略证据（示例）
grep -n "CHANNEL_" src/runtime/uns.py            # 六路感知枚举
grep -n "credibility" src/runtime/env_perception.py   # 可信分级门
ls src/runtime/env_sources/                      # 三类环境源适配器
grep -n "role.*SUPERADMIN" src/runtime/authn/deps.py  # P0 位置
```

---

*审计方法遵循 `system-alignment` 技能：所有状态均来自 grep/行号/测试输出/基准数据，不采信文档自述。代码审计子代理深度扫描结论已并入 §4.2/§4.3。P0 与多租户隔离主干已于审计同日（2026-07-27）修复，全量回归 **246 passed 零回归**。*
