"""Live-data 适配器骨架（GitHub #3 · HubPort 启发：创建时 AI 辅助 / 运行时确定性）

把"演示态种子 JSON"平滑切换到"现场态真实源"（OPC-UA / MQTT / REST）的示范骨架。

🔴 设计纪律（EXTERNAL_NARRATIVE §16）：
- 运行时确定性：无论骨架是否 AI 生成，fetch_snapshot() 返回的数据**契约形状**
  必须与 demo_seed.py 注入的种子一致（字段 / 嵌套 / 单位不变），对外 Agent 接口零改动。
- 韧性降级：超时 / 不可达显式抛异常，调用方据此回退种子（与 4.4 铁律对齐）。
- 零明文：连接参数走 env / 请求配置，绝不明文落库 / 日志。
- 零真名：示例不含任何真实公司 / 设备名（研究案例匿名铁律）。

落点（#3）：
- BaseLiveAdapter：抽象 connect() / fetch_snapshot() / health()；统一两类异常。
- RestMesAdapter：httpx.AsyncClient 拉 MES 工单 / 设备状态，映射为与种子同形状 dict。

切换开关复用 src/runtime/main.py 的 ZHIYAN_DEMO_DATA（不新造 SEED_MODE）：
    if os.getenv("ZHIYAN_DEMO_DATA") == "1": seed else: adapter
"""
from __future__ import annotations

import abc
import os
import time
from typing import Any, Dict, Optional

# 超时阈值（与 4.4 铁律、前端一致：8s）
DEFAULT_TIMEOUT_S = 8.0


class AdapterTimeout(Exception):
    """连接 / 抓取超过阈值（>8s）时抛出，调用方回退种子。"""


class AdapterUnreachable(Exception):
    """数据源不可达（DNS / 拒绝 / 401 等）时抛出，调用方回退种子。"""


class BaseLiveAdapter(abc.ABC):
    """现场态数据源适配器基类。

    子类只需实现 connect() 与 fetch_snapshot()；health() 默认按能否连通判断。
    fetch_snapshot() 的返回**必须**与 demo_seed 同形状（契约保形）。
    """

    # 子类可声明契约字段（用于运行时契约校验 / 单测）
    CONTRACT_FIELDS: tuple = ("work_orders", "equipment_status")

    def __init__(self, base_url: str = "", api_key: str = "", tenant_id: str = "default",
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self.base_url = base_url
        self.api_key = api_key  # 仅持有引用，绝不打印 / 落库
        self.tenant_id = tenant_id
        self.timeout = timeout
        self._connected = False

    @abc.abstractmethod
    async def connect(self) -> None:
        """建立连接（握手 / 鉴权）。失败抛 AdapterUnreachable。"""
        raise NotImplementedError

    @abc.abstractmethod
    async def fetch_snapshot(self) -> Dict[str, Any]:
        """抓取一份与种子同形状的快照。超时抛 AdapterTimeout，不可达抛 AdapterUnreachable。"""
        raise NotImplementedError

    async def health(self) -> Dict[str, Any]:
        t0 = time.monotonic()
        try:
            await self.connect()
            ok = True
            err = ""
        except AdapterUnreachable as e:
            ok, err = False, f"unreachable: {e}"
        except AdapterTimeout as e:
            ok, err = False, f"timeout: {e}"
        except Exception as e:  # 兜底：任何异常都判不可达，绝不阻断管道
            ok, err = False, f"{type(e).__name__}: {e}"
        return {
            "ok": ok,
            "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            "detail": err or "connected",
        }

    def _assert_contract(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """契约保形校验：缺失核心字段视为不可达（数据不可用），而非静默返回。"""
        missing = [f for f in self.CONTRACT_FIELDS if f not in snapshot]
        if missing:
            raise AdapterUnreachable(f"契约缺失字段: {missing}")
        return snapshot


class RestMesAdapter(BaseLiveAdapter):
    """MES REST 示例适配器（httpx 异步客户端）。

    假设 MES 暴露：
        GET {base_url}/work-orders      -> [{order_no, material, qty, due, status}]
        GET {base_url}/equipment-status -> [{equip_id, state, oee}]
    映射为与 demo_seed 同形状：
        {
          "work_orders": [...],
          "equipment_status": [...],
        }
    真实字段名以客户 MES 为准；此处仅为「骨架 + 字段映射草稿」示范。
    """

    async def connect(self) -> None:
        import httpx
        if not self.base_url:
            raise AdapterUnreachable("base_url 未配置")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 轻量握手：HEAD 根路径（或 /health），失败即不可达
                r = await client.head(self.base_url, headers=self._headers())
                if r.status_code >= 400:
                    raise AdapterUnreachable(f"握手返回 {r.status_code}")
            self._connected = True
        except AdapterUnreachable:
            raise
        except httpx.TimeoutException as e:
            raise AdapterTimeout(f"连接超时: {e}") from e
        except Exception as e:
            raise AdapterUnreachable(f"连接失败: {type(e).__name__}: {e}") from e

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def fetch_snapshot(self) -> Dict[str, Any]:
        import httpx
        await self.connect()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                wo = await client.get(f"{self.base_url}/work-orders", headers=self._headers())
                eq = await client.get(f"{self.base_url}/equipment-status", headers=self._headers())
                if wo.status_code >= 400 or eq.status_code >= 400:
                    raise AdapterUnreachable(
                        f"抓取返回 {wo.status_code}/{eq.status_code}")
                snapshot = {
                    "work_orders": wo.json(),
                    "equipment_status": eq.json(),
                }
                return self._assert_contract(snapshot)
        except (AdapterUnreachable, AdapterTimeout):
            raise
        except httpx.TimeoutException as e:
            raise AdapterTimeout(f"抓取超时: {e}") from e
        except Exception as e:
            raise AdapterUnreachable(f"抓取失败: {type(e).__name__}: {e}") from e


def make_adapter(kind: str, base_url: str = "", api_key: str = "",
                 tenant_id: str = "default") -> Optional[BaseLiveAdapter]:
    """工厂：按 kind 选择适配器（扩展点：OPC-UA / MQTT 后续补子类）。"""
    kind = (kind or "").lower()
    if kind in ("mes", "erp"):
        return RestMesAdapter(base_url=base_url, api_key=api_key, tenant_id=tenant_id)
    # 其余类型尚未实现骨架，返回 None（调用方回退种子）
    return None
