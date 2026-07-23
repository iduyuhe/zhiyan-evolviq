"""租户存储——内存注册表 + 数据库持久化（韧性降级）

- db 可用：租户与密钥落库（tenants 表），重启后从库恢复。
- db 不可用（no-op 降级）：仅内存持有，保证多租户逻辑仍可运行，只是重启即失。
- 默认租户 `default` 在 init() 时确保存在；其密钥为内存随机生成（仅当 db 不可用时），
  若 db 可用则优先保留库中原值。
"""

import json
import logging

from sqlalchemy import select

from src.common import db
from src.runtime.models.tenant import DEFAULT_TENANT_ID, Tenant, gen_key, hash_key

logger = logging.getLogger(__name__)


class TenantStore:
    """租户注册表（进程级单例语义）"""

    def __init__(self):
        self._by_id: dict[str, Tenant] = {}
        self._by_key_hash: dict[str, str] = {}  # api_key_hash -> tenant_id

    # ---------- 生命周期 ----------
    async def init(self) -> None:
        """确保默认租户存在，并从库加载全部租户到内存。

        调用时机：main lifespan 在 init_db() 之后、任何需要 tenant 的组件之前。
        """
        if not db.db_available or db.async_session is None:
            self._ensure_default_memory()
            logger.warning("⚠️ 租户存储降级为内存态（db 不可用），重启即失")
            return
        try:
            async with db.async_session() as s:
                rows = (await s.execute(select(Tenant))).scalars().all()
                for t in rows:
                    self._by_id[t.id] = t
                    self._by_key_hash[t.api_key_hash] = t.id
        except Exception as e:
            logger.warning(f"⚠️ 租户加载失败，降级内存态：{e}")
        if DEFAULT_TENANT_ID not in self._by_id:
            await self._create(DEFAULT_TENANT_ID, "默认租户")

    def _ensure_default_memory(self) -> None:
        if DEFAULT_TENANT_ID in self._by_id:
            return
        key = gen_key()
        t = Tenant(id=DEFAULT_TENANT_ID, name="默认租户", api_key_hash=hash_key(key))
        self._by_id[DEFAULT_TENANT_ID] = t
        self._by_key_hash[t.api_key_hash] = DEFAULT_TENANT_ID

    async def _create(self, tid: str, name: str) -> tuple[str, str]:
        key = gen_key()
        t = Tenant(id=tid, name=name, api_key_hash=hash_key(key), is_active=True)
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    s.add(t)
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 租户持久化失败（仅内存）：{e}")
        self._by_id[tid] = t
        self._by_key_hash[t.api_key_hash] = tid
        return tid, key

    # ---------- 操作 ----------
    async def register(self, name: str) -> tuple[str, str]:
        """注册新租户，返回 (tenant_id, 明文 api_key)。明文仅此一次可见。"""
        tid = gen_key()[:12]  # 复用同形 id
        # 避免 id 碰撞
        while tid in self._by_id:
            tid = gen_key()[:12]
        return await self._create(tid, name)

    async def resolve(self, api_key: str | None) -> str | None:
        """用明文密钥解析 tenant_id；无效/停用返回 None。"""
        if not api_key:
            return None
        h = hash_key(api_key)
        tid = self._by_key_hash.get(h)
        t = self._by_id.get(tid) if tid else None
        # 内存态（未落库）的 ORM 实例 is_active 可能为 None，按"未显式停用即有效"处理
        if t and t.is_active is not False:
            return tid
        return None

    def get(self, tid: str) -> Tenant | None:
        return self._by_id.get(tid)

    def list(self) -> list[Tenant]:
        return list(self._by_id.values())

    async def rotate(self, tid: str) -> str | None:
        """轮换租户密钥，返回新的明文 api_key；仅此一次可见。"""
        t = self._by_id.get(tid)
        if not t:
            return None
        new_key = gen_key()
        self._by_key_hash.pop(t.api_key_hash, None)
        t.api_key_hash = hash_key(new_key)
        self._by_key_hash[t.api_key_hash] = tid
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(Tenant, tid)
                    if obj:
                        obj.api_key_hash = t.api_key_hash
                        await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 密钥持久化失败（内存已更新）：{e}")
        return new_key

    async def set_gateway_config(self, tid: str, config: dict | None) -> bool:
        """设置/清除租户网关连接参数覆写（None 表示恢复平台共享网关）。"""
        t = self._by_id.get(tid)
        if not t:
            return False
        t.gateway_config = json.dumps(config, ensure_ascii=False) if config else None
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(Tenant, tid)
                    if obj:
                        obj.gateway_config = t.gateway_config
                        await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 网关配置持久化失败（内存已更新）：{e}")
        return True

    def get_gateway_config(self, tid: str) -> dict | None:
        t = self._by_id.get(tid)
        if t and t.gateway_config:
            try:
                return json.loads(t.gateway_config)
            except Exception:
                return None
        return None

    async def delete(self, tid: str) -> bool:
        """删除租户（默认租户不可删）。返回是否成功。"""
        if tid == DEFAULT_TENANT_ID:
            return False
        t = self._by_id.pop(tid, None)
        if t:
            self._by_key_hash.pop(t.api_key_hash, None)
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    obj = await s.get(Tenant, tid)
                    if obj:
                        await s.delete(obj)
                        await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ 租户删除持久化失败（内存已移除）：{e}")
        return t is not None


# 进程级单例
tenant_store = TenantStore()
