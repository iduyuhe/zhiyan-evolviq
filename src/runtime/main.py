"""智衍 EvolvIQ Runtime — FastAPI入口"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src.runtime.api import agents_api, auth, audit, events_api, health, mcp_tools, scheduler_api, sessions, supply_chain
from src.runtime.api import interventions, reports, system, knowledge_graph, gateways, strategy, tenants, experience, evolution, data_sources
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
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(supply_chain.router)
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(mcp_tools.router)
app.include_router(scheduler_api.router)
app.include_router(events_api.router)
app.include_router(agents_api.router)
app.include_router(interventions.router)
app.include_router(reports.router)
app.include_router(system.router)
app.include_router(knowledge_graph.router)
app.include_router(gateways.router)
app.include_router(strategy.router)
app.include_router(experience.router)
app.include_router(evolution.router)
app.include_router(tenants.router)
app.include_router(data_sources.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.runtime.main:app", host="0.0.0.0", port=8000, reload=True)
