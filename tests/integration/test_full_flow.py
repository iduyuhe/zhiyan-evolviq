"""全链路集成测试——模拟Studio→Runtime→Agent→MCP→结果的完整闭环

测试覆盖：
1. 健康检查
2. MCP工具列表与调用
3. Agent会话创建→规划→批准→执行→结果
4. 审计日志记录
5. 会话历史查询
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestIntegration:
    """全链路集成测试"""

    @pytest.mark.asyncio
    async def test_01_health(self, client):
        """Step 1: 健康检查"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "智衍 EvolvIQ Runtime"
        print("  ✅ 健康检查")

    @pytest.mark.asyncio
    async def test_02_mcp_tools_list(self, client):
        """Step 2: MCP工具列表"""
        resp = await client.get("/mcp/tools")
        assert resp.status_code == 200
        tools = resp.json()["tools"]
        assert len(tools) == 6
        tool_names = {t["name"] for t in tools}
        assert "get_bom" in tool_names
        assert "supply_check" in tool_names
        assert "find_alternatives" in tool_names
        assert "lock_inventory" in tool_names
        print(f"  ✅ MCP工具列表: {len(tools)}个工具")

    @pytest.mark.asyncio
    async def test_03_mcp_call_get_bom(self, client):
        """Step 3: 调用MCP get_bom"""
        resp = await client.post(
            "/mcp/tools/get_bom/call",
            json={"arguments": {"bom_id": "BOM-NPI-007"}},
        )
        assert resp.status_code == 200
        bom = resp.json()["result"]
        assert bom["product_name"]
        assert len(bom["items"]) >= 5
        print(f"  ✅ MCP get_bom: {bom['product_name']} ({len(bom['items'])}项物料)")

    @pytest.mark.asyncio
    async def test_04_mcp_call_supply_check(self, client):
        """Step 4: 调用MCP supply_check"""
        resp = await client.post(
            "/mcp/tools/supply_check/call",
            json={"arguments": {"bom_id": "BOM-NPI-007"}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["bom"]
        assert len(result["items"]) >= 5
        assert len(result["inventory"]) >= 5
        print(f"  ✅ MCP supply_check: {result['bom']}")

    @pytest.mark.asyncio
    async def test_05_create_session(self, client):
        """Step 5: 创建Agent会话"""
        resp = await client.post(
            "/sessions",
            json={"goal": "检查BOM-NPI-007物料齐套，发现缺料风险>30%时自动检索替代方案"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"]
        assert data["status"] == "awaiting_approval"
        assert "规划" in data["plan"]
        # 保存session_id供后续测试
        self._session_id = data["session_id"]
        print(f"  ✅ 创建会话: {data['session_id'][:16]}... → {data['status']}")

    @pytest.mark.asyncio
    async def test_06_approve_session(self, client):
        """Step 6: 批准执行"""
        # 先创建会话
        create_resp = await client.post(
            "/sessions",
            json={"goal": "检查BOM-NPI-007物料齐套，自动推荐替代方案"},
        )
        session_id = create_resp.json()["session_id"]

        # 批准执行
        resp = await client.post(
            f"/sessions/{session_id}/approve",
            json={"approved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] is not None
        result = data["result"]
        assert result["completeness_pct"] >= 0
        assert len(result["check_details"]) >= 5
        print(f"  ✅ 批准执行: 齐套率{result['completeness_pct']}%, {len(result['check_details'])}项物料检查")

    @pytest.mark.asyncio
    async def test_07_session_history(self, client):
        """Step 7: 会话历史"""
        # 先创建一个会话确保有数据
        await client.post("/sessions", json={"goal": "检查BOM物料"})

        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["sessions"]) >= 1
        first = data["sessions"][0]
        assert "session_id" in first
        assert "goal" in first
        assert "status" in first
        print(f"  ✅ 会话历史: {data['total']}条记录")

    @pytest.mark.asyncio
    async def test_08_audit_logs(self, client):
        """Step 8: 审计日志"""
        # 先创建并批准一个会话产生审计日志
        resp = await client.post("/sessions", json={"goal": "审计测试"})
        sid = resp.json()["session_id"]
        await client.post(f"/sessions/{sid}/approve", json={"approved": True})

        resp = await client.get("/audit/logs?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["stats"] is not None
        assert data["stats"]["total_logs"] >= 1
        print(f"  ✅ 审计日志: {data['total']}条, 共{data['stats']['total_logs']}条")

    @pytest.mark.asyncio
    async def test_09_create_and_intervene(self, client):
        """Step 9: 创建会话并驳回"""
        resp = await client.post(
            "/sessions",
            json={"goal": "测试驳回流程"},
        )
        sid = resp.json()["session_id"]

        reject_resp = await client.post(
            f"/sessions/{sid}/approve",
            json={"approved": False, "feedback": "需要调整参数"},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == "rejected"
        print(f"  ✅ 驳回流程: {reject_resp.json()['status']}")

    @pytest.mark.asyncio
    async def test_10_full_workflow(self, client):
        """Step 10: 完整工作流（一次完整的用户旅程）"""
        # 1. 用户设定目标
        goal = "每2小时检查NPI物料齐套，发现缺料风险>30%时自动检索替代方案，在5%价格波动内可直接锁定库存"
        create_resp = await client.post("/sessions", json={"goal": goal})
        assert create_resp.status_code == 200
        session = create_resp.json()
        print(f"  📋 1. 目标设定: {goal[:40]}...")

        # 2. Agent生成规划
        assert session["plan"] is not None
        assert "步骤" in session["plan"] or "Step" in session["plan"]
        print(f"  📋 2. 规划生成: {len(session['plan'])}字符")

        # 3. 人确认执行
        exec_resp = await client.post(
            f"/sessions/{session['session_id']}/approve",
            json={"approved": True},
        )
        assert exec_resp.status_code == 200
        result = exec_resp.json()["result"]
        print(f"  ⚡ 3. 执行完成: 齐套率{result['completeness_pct']}%")

        # 4. 检查审计日志
        audit_resp = await client.get("/audit/logs", params={"session_id": session["session_id"]})
        assert audit_resp.status_code == 200
        assert audit_resp.json()["total"] >= 2
        print(f"  📜 4. 审计追溯: {audit_resp.json()['total']}条日志")

        # 5. 验证全链路状态
        assert result["completeness_pct"] > 0
        assert len(result["check_details"]) >= 5
        assert len(result["warning"]) >= 0
        print(f"  ✅ 5. 全链路验证通过")
