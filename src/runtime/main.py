"""智衍 EvolvIQ Runtime — FastAPI入口"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.runtime.api import agents_api, auth, audit, events_api, health, mcp_tools, scheduler_api, sessions, supply_chain
from src.runtime.api import interventions, reports, system, knowledge_graph, gateways, strategy, tenants, experience, evolution, data_sources, twin, governance
from src.runtime.federation import api as federation_api
from src.runtime.authn import api as authn_api
from src.runtime.api import writeback as writeback_api
from src.runtime.api import monitoring as monitoring_api
from src.runtime.core.scheduler import scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("zhiyan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 智衍 EvolvIQ Runtime starting...")
    logger.info(f"  Version: 0.1.0")
    logger.info(f"  Mode: MVP")
    scheduler.start()
    # 数据层落库（T2）：建表 + 韧性探测；PostgreSQL 不可达时自动回退本地 SQLite
    from src.common.db import init_db, db_status
    from src.runtime.persistence import log_audit
    from src.meta_agent.audit import audit_logger

    db_ok = await init_db()
    if db_ok:
        audit_logger.attach_sink(log_audit)
        await audit_logger.hydrate(limit=500)  # 审计历史回灌内存（重启可追溯）
        # 效果指标：挂载落库 sink + 回灌（重启后效果信号不丢，支撑按效果调参）
        from src.runtime.core.metrics import metrics
        from src.runtime.persistence import save_metric_record
        metrics.attach_sink(save_metric_record)
        await metrics.hydrate(limit=500)
        # 经验反馈（P1）：挂载落库 sink + 回灌（偏好/禁忌记忆跨重启累积）
        from src.runtime.experience import experience
        from src.runtime.persistence import save_feedback_record
        experience.attach_sink(save_feedback_record)
        await experience.hydrate(limit=500)
        # 自进化（P2）：Prompt 版本库 + KG 事实提议 挂载落库 sink + 回灌
        from src.runtime.evolution import prompt_versions, kg_facts
        from src.runtime.persistence import save_prompt_version, save_kg_fact_proposal
        prompt_versions.attach_sink(save_prompt_version)
        await prompt_versions.hydrate(limit=500)
        kg_facts.attach_sink(save_kg_fact_proposal)
        await kg_facts.hydrate(limit=500)
        st = db_status()
        logger.info(f"📦 数据层已接入 [{st['mode']}] {st['url']}")
    else:
        logger.warning("⚠️ 数据层不可用，持久化降级为 no-op（执行管道不受影响）")

    # 多租户：确保默认租户存在并从库加载全部租户（db 不可用时降级内存态）
    from src.runtime.tenant_store import tenant_store
    await tenant_store.init()
    logger.info("🏢 租户存储已初始化")

    # 企业认证：确保超级管理员账号存在（DB 不可用时降级内存态；测试可直接调用）
    from src.runtime.authn.service import authn_service
    await authn_service.ensure_admin()
    await authn_service.sync_admin_password()  # 按 ZHIYAN_ADMIN_PASSWORD 同步（仅启动期）
    logger.info("🔐 企业认证模块已就绪（本地/LDAP/OAuth2 + JWT/RBAC）")

    # 行业知识库模板：按 ZHIYAN_INDUSTRY 注入对应种子（船舶/铁路/电子…）
    industry = os.environ.get("ZHIYAN_INDUSTRY", "").strip()
    if industry:
        from src.runtime.seed import bootstrap_industry

        seed_summary = bootstrap_industry(industry)
        logger.info(f"🧩 行业知识库注入：{seed_summary}")

    # 数据接入层（P1）：从环境变量装载数据源（MES/ERP/PLM/WMS/时序库）。
    # 未配置项不注册，agent 自动回退 seed；真实系统不可达时连接器韧性降级。
    from src.runtime.data_sources import config as ds_config
    from src.runtime.data_sources import registry as ds_registry

    ds_config.load_default_sources()
    for t in tenant_store.list():
        if t.id != "default":
            ds_config.load_sources_for_tenant(t.id)
    # 从库回灌多租户数据源配置（P2-2）：API 注入且持久化的配置，重启后自动重新注册
    try:
        from src.runtime.persistence import load_tenant_data_sources
        for cfg in await load_tenant_data_sources():
            ds_config.register_from_config(cfg["tenant_id"], cfg["kind"], cfg["config"])
    except Exception as e:
        logger.warning(f"⚠️ 多租户数据源回灌失败（已忽略）：{e}")
    logger.info(f"📡 数据接入层已初始化：{[s._key() for s in ds_registry.list()]}")

    # 知识图谱（V1-1）：Neo4j 不可达自动回退内存图；从种子构建跨 Agent 语义网
    from src.common import neo4j_client as neo
    from src.runtime import knowledge_graph as kg

    neo_ok = await neo.init_neo4j()
    if neo_ok:
        stats = await kg.build_from_seeds()
        logger.info(f"🕸️ 知识图谱已构建 [{neo.neo_mode}] 节点={stats['total_nodes']} 边={stats['total_edges']}")
        # 实时闭环（P2-1）：后台周期从数据源同步 live 数据进图谱
        try:
            import asyncio as _asyncio
            _asyncio.create_task(kg.graph_sync_loop(interval=300))
            logger.info("🔄 图谱实时同步循环已启动（每 300s）")
        except Exception:
            pass
    else:
        logger.warning("⚠️ 知识图谱不可用，降级为 no-op")

    # 工业协议网关（V1-3）：best-effort 初始化四类网关（Modbus/MQTT/OPC-UA/IPC-CFX）；
    # 真实 Server/Broker 不可达时自动回退模拟模式，绝不阻断启动
    from src.gateways.manager import manager as gw_manager

    gw_summary = await gw_manager.initialize()
    logger.info(f"🛰️ 网关管理器已初始化：{gw_summary}")

    # 监控告警（v28.3）：后台周期检测回写积压 + 网关断流（登录异常由 authn 实时上报）
    try:
        import asyncio as _asyncio
        from src.runtime.monitoring import alert_check_loop
        _asyncio.create_task(alert_check_loop(interval=60))
        logger.info("🚨 监控告警循环已启动（每 60s）")
    except Exception:
        pass

    # 演示审计接收端（v29.2）：ZHIYAN_DS_DEMO_AUDIT=1 时，启动线程内 HTTP 接收端
    # 并把 MES/ERP 连接器指向它，使回写实执行路径（真实 HTTP POST→200）闭环，
    # 不依赖外部 ERP/MES；生产改用真实 ZHIYAN_DS_MES_URL/ERP_URL 同样生效。
    if os.environ.get("ZHIYAN_DS_DEMO_AUDIT") == "1":
        try:
            from src.runtime.data_sources.demo_audit_sink import start
            from src.runtime.data_sources.connectors.domain import MesConnector, ErpConnector
            sink_port = int(os.environ.get("ZHIYAN_DS_DEMO_AUDIT_PORT", "8800"))
            start(sink_port)
            sink_base = f"http://127.0.0.1:{sink_port}"
            ds_registry.register(MesConnector(base_url=sink_base, api_key="demo", tenant_id="default"))
            ds_registry.register(ErpConnector(base_url=sink_base, api_key="demo", tenant_id="default"))
            logger.info(f"🧪 演示审计：MES/ERP 连接器已指向 {sink_base}（回写实执行闭环）")
        except Exception as e:
            logger.warning(f"⚠️ 演示审计接收端启动失败（已忽略）：{e}")

    # 演示效果信号种子（可选）：仅当 ZHIYAN_DEMO_DATA=1 时注入，
    # 让「按效果调参」在无真实流量时也能跑出可信的效果信号与建议（不污染测试/生产）。
    if os.environ.get("ZHIYAN_DEMO_DATA") == "1":
        from src.runtime.core import demo_seed
        demo_summary = demo_seed.seed_demo_data()
        logger.info(f"🎬 演示效果信号种子：{demo_summary}")

    yield
    scheduler.stop()
    logger.info("👋 智衍 EvolvIQ Runtime shutting down")


app = FastAPI(
    title="智衍 EvolvIQ Runtime API",
    description="AI原生工业智能体开发与部署平台 · Runtime核心",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
async def root_index() -> RedirectResponse:
    """根路径自动跳转到 Swagger 交互文档（避免 FastAPI 默认 404 体验差）"""
    return RedirectResponse(url="/docs", status_code=307)


# CORS（MVP阶段允许本地前端跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
# 全局鉴权门禁：除健康探针(/health)与认证端点(/authn/*，含登录)外，
# 所有路由挂 require_auth 依赖——ZHIYAN_AUTH_REQUIRE=1 时强制 Bearer JWT，
# 否则放行并返回匿名上下文（兼容 150+ 既有测试与不带 token 的 e2e 脚本）。
from fastapi import Depends
from src.runtime.authn.deps import require_auth

_AUTH_DEPS = [Depends(require_auth)]

app.include_router(health.router)  # 公开：探针
app.include_router(sessions.router, dependencies=_AUTH_DEPS)
app.include_router(supply_chain.router, dependencies=_AUTH_DEPS)
app.include_router(auth.router, dependencies=_AUTH_DEPS)  # /auth/boundaries 授权边界
app.include_router(audit.router, dependencies=_AUTH_DEPS)
app.include_router(mcp_tools.router, dependencies=_AUTH_DEPS)
app.include_router(scheduler_api.router, dependencies=_AUTH_DEPS)
app.include_router(events_api.router, dependencies=_AUTH_DEPS)
app.include_router(agents_api.router, dependencies=_AUTH_DEPS)
app.include_router(interventions.router, dependencies=_AUTH_DEPS)
app.include_router(reports.router, dependencies=_AUTH_DEPS)
app.include_router(system.router, dependencies=_AUTH_DEPS)
app.include_router(knowledge_graph.router, dependencies=_AUTH_DEPS)
app.include_router(gateways.router, dependencies=_AUTH_DEPS)
app.include_router(strategy.router, dependencies=_AUTH_DEPS)
app.include_router(experience.router, dependencies=_AUTH_DEPS)
app.include_router(evolution.router, dependencies=_AUTH_DEPS)
app.include_router(tenants.router, dependencies=_AUTH_DEPS)
app.include_router(data_sources.router, dependencies=_AUTH_DEPS)
app.include_router(twin.router, dependencies=_AUTH_DEPS)
app.include_router(governance.router, dependencies=_AUTH_DEPS)
app.include_router(federation_api.router, dependencies=_AUTH_DEPS)
app.include_router(writeback_api.router, dependencies=_AUTH_DEPS)  # ERP/MES 回写审计桥
app.include_router(monitoring_api.router, dependencies=_AUTH_DEPS)  # 监控告警（v28.3）
app.include_router(authn_api.router)  # 公开：登录/后端发现/OAuth 回调


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.runtime.main:app", host="0.0.0.0", port=8000, reload=True)
