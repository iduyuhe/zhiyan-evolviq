"""知识图谱闭环测试（内存图模式，验证构建/桥接/查询/增量写入）"""

import pytest

from src.common import neo4j_client as neo
from src.runtime import knowledge_graph as kg


@pytest.fixture(autouse=True)
async def _memory_kg():
    # 强制内存图模式，避开沙箱无 Neo4j 服务的网络探测，聚焦于图谱逻辑
    neo.driver = None
    neo.neo_mode = "memory"
    neo.neo_available = True
    await kg.build_from_seeds()
    yield
    await neo.clear_graph()


async def test_build_produces_nodes_and_edges():
    stats = await neo.graph_stats()
    assert stats["total_nodes"] > 0
    assert stats["total_edges"] > 0
    for lbl in ("Material", "Equipment", "Product", "DefectCase", "Line"):
        assert lbl in stats["nodes_by_label"], f"缺少节点类型 {lbl}"


async def test_cross_agent_bridge_quality_to_equipment():
    # 质量案例应通过关键词匹配桥接到 PM 设备（跨 Agent 语义）
    nb = await neo.get_neighbors("CASE:CASE-2026-001", edge="怀疑设备")
    assert nb, "质量案例应桥接到 PM 设备"
    assert any(n["id"].startswith("EQP:") for n in nb)


async def test_equipment_parts_bridge():
    nb = await neo.get_neighbors("EQP:scanner_1", edge="有部件")
    assert nb, "设备应有部件"
    assert all(n["id"].startswith("PART:") for n in nb)


async def test_line_shared_across_agents():
    # SMT-L01 应被 OEE/SMT/AOI 三个 Agent 共享（联邦节点）
    node = await neo.get_node("LINE:SMT-L01")
    assert node
    assert "Line" in node["labels"]


async def test_query_material_by_category():
    nodes = await neo.query_nodes("Material", category="三极管")
    assert nodes
    assert all(n["props"].get("category") == "三极管" for n in nodes)


async def test_apply_execution_lock_alternative():
    # 事实锚点：供应链锁定替代动作增量写入图谱，不改动任何数字
    result = {"actions_taken": [
        {"type": "lock_alternative", "material_code": "PCB-0001", "alt_code": "二极管-0002", "status": "auto"}
    ]}
    await kg.apply_execution_result("supply_chain", "sess-x", result)
    nb = await neo.get_neighbors("MAT:PCB-0001", edge="锁定替代")
    assert nb, "锁定替代边应写入图谱"
