"""F1 回归测试：决策结果卡数据源标注（'real' / 'demo'）。

应用型可信度底座——确保接口层在返回决策结果时，按租户是否接入真实信号源
注入 data_source 字段，前端据此渲染「真实客户信号 / 演示数据」徽标，
绝不把演示种子数据冒充真实客户数据。
"""

from __future__ import annotations

import os

import httpx
import pytest
from fastapi import FastAPI, Request

from src.runtime.real_source.dute_real import is_real_source_active


# --------------------------------------------------------------------------
# 1) 纯单测：is_real_source_active 开关与租户判定
# --------------------------------------------------------------------------

def test_is_real_source_active_default_dute_is_real():
    os.environ.pop("ZHIYAN_DUTE_REAL", None)
    # 默认（ZHIYAN_DUTE_REAL 未设 → '1'）且租户为真实信号源归属租户 'dute'
    assert is_real_source_active("dute") is True
    # 其它租户不被视为真实源
    assert is_real_source_active("telecom") is False
    assert is_real_source_active("default") is False


def test_is_real_source_active_disabled():
    os.environ["ZHIYAN_DUTE_REAL"] = "0"
    try:
        assert is_real_source_active("dute") is False
    finally:
        os.environ["ZHIYAN_DUTE_REAL"] = "1"


# --------------------------------------------------------------------------
# 2) 接口层：quick-check 注入 data_source（demo / real）
# --------------------------------------------------------------------------

FAKE_RESULT = {
    "status": "completed",
    "summary": "演示结论",
    "bom": "SMIC-28nm-Logic",
    "completeness_pct": 100,
    "check_details": [],
    "actions_taken": [],
    "warning": [],
}


@pytest.fixture
async def client(monkeypatch):
    from src.runtime.api import sessions as s_mod
    from src.runtime.api.deps import get_tenant

    app = FastAPI()
    app.include_router(s_mod.router)

    # 租户从请求头 X-Tenant-Key 读取，便于同一 fixture 测两种租户
    def _tenant_from_header(request: Request) -> str:
        return request.headers.get("X-Tenant-Key", "telecom")

    app.dependency_overrides[get_tenant] = _tenant_from_header

    class FakeEngine:
        async def plan(self, *a, **k):
            return {}
        async def execute(self, *a, **k):
            return dict(FAKE_RESULT)

    monkeypatch.setattr(s_mod, "get_engine", lambda: FakeEngine())
    # 避免测试中触发计量/埋点副作用（需要 DB）；原函数为 async，stub 也须 async
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(s_mod, "_meter_insight", _noop)
    monkeypatch.setattr(s_mod, "_track_session_start", _noop)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def test_quick_check_demo_tenant(client):
    r = await client.post(
        "/sessions/quick-check",
        json={"goal": "检查 BOM 齐套率"},
        headers={"X-Tenant-Key": "telecom"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["result"]["data_source"] == "demo"


async def test_quick_check_real_tenant(client):
    # dute 是真实信号源归属租户，且 ZHIYAN_DUTE_REAL 默认启用 → 标 real
    r = await client.post(
        "/sessions/quick-check",
        json={"goal": "检查 BOM 齐套率"},
        headers={"X-Tenant-Key": "dute"},
    )
    assert r.status_code == 200
    assert r.json()["result"]["data_source"] == "real"
