"""智衍 EvolvIQ Runtime — FastAPI入口"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.runtime.api import agents_api, auth, audit, events_api, health, mcp_tools, scheduler_api, sessions, supply_chain
from src.runtime.api import interventions, reports, system, knowledge_graph, gateways, strategy, tenants
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
        st = db_status()
        logger.info(f"📦 数据层已接入 [{st['mode']}] {st['url']}")
    else:
        logger.warning("⚠️ 数据层不可用，持久化降级为 no-op（执行管道不受影响）")

    # 多租户：确保默认租户存在并从库加载全部租户（db 不可用时降级内存态）
    from src.runtime.tenant_store import tenant_store
    await tenant_store.init()
    logger.info("🏢 租户存储已初始化")

    # 知识图谱（V1-1）：Neo4j 不可达自动回退内存图；从种子构建跨 Agent 语义网
    from src.common import neo4j_client as neo
    from src.runtime import knowledge_graph as kg

    neo_ok = await neo.init_neo4j()
    if neo_ok:
        stats = await kg.build_from_seeds()
        logger.info(f"🕸️ 知识图谱已构建 [{neo.neo_mode}] 节点={stats['total_nodes']} 边={stats['total_edges']}")
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
app.include_router(tenants.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.runtime.main:app", host="0.0.0.0", port=8000, reload=True)
