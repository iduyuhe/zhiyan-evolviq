"""多租户隔离测试——验证行级隔离（会话/授权边界）与知识图谱 tenant 标签

设计：用 httpx ASGITransport 直连 app（不触发 lifespan，tenant_store 走内存态）。
租户注册接口在内存态即可工作；会话/授权边界隔离验证内存引擎与内存图谱。
"""

import httpx
import pytest

from src.common import neo4j_client as neo
from src.runtime import knowledge_graph as kg

pytestmark = pytest.mark.asyncio


@pytest.fixture
def client():
    from src.runtime.main import app

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_tenant_isolation_sessions_and_boundaries(client):
    # 1) 自助注册两个租户，拿明文 key
    rA = await client.post("/tenants/register", json={"name": "租户A"})
    rB = await client.post("/tenants/register", json={"name": "租户B"})
    assert rA.status_code == 200 and rB.status_code == 200
    keyA, keyB = rA.json()["api_key"], rB.json()["api_key"]
    hA, hB = {"X-Tenant-Key": keyA}, {"X-Tenant-Key": keyB}

    # 2) 无效 key → 401
    bad = await client.get("/sessions", headers={"X-Tenant-Key": "not-a-real-key"})
    assert bad.status_code == 401

    # 3) 两个租户各建一个会话
    sA = await client.post("/sessions", json={"goal": "A的目标"}, headers=hA)
    sB = await client.post("/sessions", json={"goal": "B的目标"}, headers=hB)
    assert sA.status_code == 200 and sB.status_code == 200
    idA, idB = sA.json()["session_id"], sB.json()["session_id"]

    # 4) 会话列表按租户隔离
    idsA = {s["session_id"] for s in (await client.get("/sessions", headers=hA)).json()["sessions"]}
    idsB = {s["session_id"] for s in (await client.get("/sessions", headers=hB)).json()["sessions"]}
    assert idA in idsA and idB not in idsA
    assert idB in idsB and idA not in idsB

    # 5) 授权边界按租户隔离：A 创建，B 不可见
    bA = await client.post(
        "/auth/boundaries",
        json={"name": "A边界", "agent": "supply_chain", "allowed_categories": ["硅片"]},
        headers=hA,
    )
    assert bA.status_code == 200
    bid = bA.json()["id"]
    assert (await client.get(f"/auth/boundaries/{bid}", headers=hB)).status_code == 404
    assert (await client.get(f"/auth/boundaries/{bid}", headers=hA)).status_code == 200
    # B 的边界列表不含 A 的边界
    bA_total = (await client.get("/auth/boundaries", headers=hA)).json()["total"]
    bB_total = (await client.get("/auth/boundaries", headers=hB)).json()["total"]
    assert bA_total == bB_total + 1  # A 比 B 多一个自定义边界


async def test_tenant_key_rotation_and_self_delete(client):
    r = await client.post("/tenants/register", json={"name": "待轮换"})
    key = r.json()["api_key"]
    tid = r.json()["tenant_id"]
    h = {"X-Tenant-Key": key}

    # 轮换后旧 key 失效、新 key 生效
    rot = await client.post("/tenants/rotate", headers=h)
    assert rot.status_code == 200
    new_key = rot.json()["api_key"]
    assert new_key != key
    assert (await client.get("/sessions", headers=h)).status_code == 401  # 旧 key 失效
    assert (await client.get("/sessions", headers={"X-Tenant-Key": new_key})).status_code == 200

    # 自带 key 删除自己
    del_r = await client.delete("/tenants/me", headers={"X-Tenant-Key": new_key})
    assert del_r.status_code == 200
    # 默认租户不可删
    del_default = await client.delete("/tenants/me")
    assert del_default.status_code == 400


async def test_knowledge_graph_tenant_tagging():
    # 直接验证图谱写入按 tenant 打标、查询可隔离
    neo._memory_nodes.clear()
    neo._memory_edges.clear()
    await kg.apply_execution_result("default", "quality_trace", "s1",
                                    {"actions_taken": [{"type": "create_capa", "case_id": "C-1"}]})
    await kg.apply_execution_result("acme", "quality_trace", "s2",
                                    {"actions_taken": [{"type": "create_capa", "case_id": "C-2"}]})

    default_nodes = await neo.query_nodes("CAPA", tenant="default")
    acme_nodes = await neo.query_nodes("CAPA", tenant="acme")

    assert any(n["props"].get("case_id") == "C-1" for n in default_nodes)
    assert all(n["props"].get("case_id") != "C-2" for n in default_nodes)
    assert any(n["props"].get("case_id") == "C-2" for n in acme_nodes)
    # 全量（不传 tenant）应包含两者
    all_nodes = await neo.query_nodes("CAPA")
    assert len(all_nodes) == 2
