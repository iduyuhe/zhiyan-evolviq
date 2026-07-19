"""数据库连接管理——韧性化

设计要点：
1. 生产目标为 PostgreSQL（config.db_url）；通过环境变量 ZHIYAN_DB_URL 可覆盖（测试/本地用）。
2. PostgreSQL 不可达时，自动回退到本地 SQLite 文件（sqlite+aiosqlite），保证「落库能力」不丢失，
   仅在日志告警，绝不抛异常中断启动或执行管道。
3. init_db() 失败则置 db_available=False，持久化层全面降级为 no-op（不破确定性管道）。
4. 模型已做方言可移植（通用 UUID / Enum），同一套 ORM 在 PG 与 SQLite 下均可建表。
"""

import logging
import os
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.runtime.models.base import Base

logger = logging.getLogger(__name__)

# 本地回退库：当 PostgreSQL 不可达时启用（数据可持久化，但非生产 PG）
_SQLITE_FALLBACK = "sqlite+aiosqlite:///./zhiyan_local.db"

engine: Optional[object] = None
async_session: Optional[async_sessionmaker] = None
db_available: bool = False
db_mode: str = "none"  # "postgresql" | "sqlite" | "none"
db_url_effective: str = ""


def _mask(url: str) -> str:
    """隐藏密码，便于日志/接口安全展示。"""
    try:
        p = urlparse(url)
        if p.password:
            netloc = f"{p.username}:***@{p.hostname}" + (f":{p.port}" if p.port else "")
            return f"{p.scheme}://{netloc}{p.path}"
        return url
    except Exception:
        return url


def _settings_db_url() -> str:
    from src.common.config import settings

    return settings.db_url


def configure_db(url: Optional[str] = None) -> None:
    """（重新）创建异步引擎与会话工厂。url 为空则读 ZHIYAN_DB_URL → config.db_url。"""
    global engine, async_session, db_url_effective
    if url is None:
        url = os.getenv("ZHIYAN_DB_URL") or _settings_db_url()
    db_url_effective = url
    # 自动纠正为 async 驱动
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, echo=False, future=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> bool:
    """建表 + 连通性探测。PG 不可达自动回退 SQLite。返回 db_available。"""
    global db_available, db_mode
    if engine is None:
        configure_db()
    # 确保领域模型类已注册到 Base.metadata（否则 create_all 建不出表）
    from src.runtime.models import agent_session, supply_chain  # noqa: F401
    # 1) 先试配置的目标库
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_available = True
        db_mode = "postgresql" if db_url_effective.startswith("postgresql") else "sqlite"
        logger.info(f"✅ 数据库就绪 [{db_mode}] {_mask(db_url_effective)}")
        return True
    except Exception as e:
        logger.warning(
            f"⚠️ 目标数据库不可达（{type(e).__name__}），回退本地 SQLite：{_SQLITE_FALLBACK}"
        )
    # 2) 回退 SQLite
    try:
        configure_db(_SQLITE_FALLBACK)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_available = True
        db_mode = "sqlite"
        logger.warning(f"⚠️ 已回退本地 SQLite（数据可持久化，非生产 PG）：{_SQLITE_FALLBACK}")
        return True
    except Exception as e2:
        logger.error(f"❌ 数据库初始化失败，持久化降级为 no-op：{type(e2).__name__} {e2}")
        db_available = False
        db_mode = "none"
        return False


async def get_db():
    if async_session is None:
        configure_db()
    async with async_session() as session:
        yield session


def db_status() -> dict:
    """对外暴露的数据库状态（含脱敏 URL）。"""
    return {
        "available": db_available,
        "mode": db_mode,
        "url": _mask(db_url_effective) if db_url_effective else None,
    }
