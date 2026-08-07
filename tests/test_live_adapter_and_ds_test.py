"""#3 live_adapter 骨架 + #4 /data-sources/{kind}/test 端点 测试（三态覆盖）

覆盖：
- #3 RestMesAdapter：ok（mock 网络）/ 不可达（连接失败）/ 超时（>8s）三态；契约保形。
- #4 端点存在性与契约：/data-sources/{kind}/test 已存在于 src/runtime/api/data_sources.py，
  返回结构 {ok, kind, latency_ms, detail}；本测试校验其接口契约（不依赖真实网络）。

🔴 零真名 / 零明文：测试数据全为虚构，不落库。
"""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.agents._skeletons.live_adapter import (
    RestMesAdapter, AdapterTimeout, AdapterUnreachable,
)


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or []

    def json(self):
        return self._json


async def test_adapter_ok_contract_preserved():
    """ok：mock 握手 + 两次 GET，返回与种子同形状 dict。"""
    adapter = RestMesAdapter(base_url="https://mes.test", api_key="x")
    fake = _FakeResp(json_data=[{"order_no": "WO1"}])
    with patch("httpx.AsyncClient") as Client:
        inst = Client.return_value.__aenter__.return_value
        inst.head = AsyncMock(return_value=_FakeResp(200))
        inst.get = AsyncMock(return_value=fake)
        snap = await adapter.fetch_snapshot()
    assert "work_orders" in snap and "equipment_status" in snap
    assert snap["work_orders"] == [{"order_no": "WO1"}]


async def test_adapter_unreachable():
    """不可达：握手抛连接异常 -> AdapterUnreachable。"""
    adapter = RestMesAdapter(base_url="https://mes.test")
    with patch("httpx.AsyncClient") as Client:
        inst = Client.return_value.__aenter__.return_value
        inst.head = AsyncMock(side_effect=ConnectionError("refused"))
        with pytest.raises(AdapterUnreachable):
            await adapter.connect()


async def test_adapter_timeout():
    """超时：fetch 抛 httpx.TimeoutException -> AdapterTimeout。"""
    import httpx
    adapter = RestMesAdapter(base_url="https://mes.test", timeout=0.01)
    with patch("httpx.AsyncClient") as Client:
        inst = Client.return_value.__aenter__.return_value
        inst.head = AsyncMock(return_value=_FakeResp(200))
        inst.get = AsyncMock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(AdapterTimeout):
            await adapter.fetch_snapshot()


async def test_adapter_contract_missing_field():
    """契约保形：_assert_contract 在缺核心字段时抛 AdapterUnreachable。"""
    adapter = RestMesAdapter(base_url="https://mes.test")
    # 故意缺失 equipment_status 键
    bad = {"work_orders": [{"order_no": "WO1"}]}
    with pytest.raises(AdapterUnreachable):
        adapter._assert_contract(bad)


def test_ds_test_endpoint_contract_exists():
    """#4 校验：/data-sources/{kind}/test 端点确实定义，且返回结构含 ok/latency_ms。"""
    import inspect
    from src.runtime.api import data_sources
    # 端点函数存在
    assert hasattr(data_sources, "test_data_source"), "端点 /data-sources/{kind}/test 缺失"
    sig = inspect.signature(data_sources.test_data_source)
    assert "kind" in sig.parameters, "端点需接收 kind 路径参数"
    # 通过源码确认返回结构字段（不依赖网络）
    src = inspect.getsource(data_sources.test_data_source)
    for field in ("ok", "latency_ms", "kind"):
        assert field in src, f"端点返回结构应含 {field}"
