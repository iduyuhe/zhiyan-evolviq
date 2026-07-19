"""端到端验证 V1-2 能力层联邦：经真实 HTTP 应用调用 11 Agent 代表工具。

用法：
    python scripts/verify_federation.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from src.runtime.main import app  # noqa: E402

OK = "✅"
FAIL = "❌"

# (tool_name, arguments) — 每个 Agent 一个代表工具，覆盖全部 11 Agent
CALLS = [
    ("supply_chain__get_bom", {"bom_id": "BOM-NPI-007"}),
    ("supply_chain__get_inventory", {"material_codes": ["PCB-0001"]}),
    ("pm_maintenance__get_equipment_list", {}),
    ("pm_maintenance__get_equipment_health", {"equipment_id": "scanner_1"}),
    ("yield_analysis__get_product_list", {}),
    ("yield_analysis__get_yield_data", {"product_id": "product_28nm_logic"}),
    ("quality_trace__get_case_list", {}),
    ("quality_trace__search_cases", {"query": "偏位"}),
    ("bom_selector__get_alternatives", {"part_no": "PCB-0001"}),
    ("dfm_check__get_rules", {}),
    ("eco_change__get_case_list", {}),
    ("ipc_standard__list_standards", {}),
    ("ipc_standard__match_judgment", {"query": "焊锡桥连"}),
    ("oee_optimizer__get_line_list", {}),
    ("oee_optimizer__get_line", {"line_id": "SMT-L01"}),
    ("smt_changeover__list_plan_keys", {}),
    ("smt_changeover__get_line_config", {"line_id": "SMT-L01"}),
    ("aoi_judge__list_line_ids", {}),
    ("aoi_judge__get_line_result", {"line_id": "SMT-L01"}),
]


def main() -> int:
    client = TestClient(app)
    failures = 0

    # 1) 联邦全景
    resp = client.get("/mcp/federation")
    assert resp.status_code == 200, resp.text
    fed = resp.json()
    print(f"{OK} GET /mcp/federation -> agents={fed['agents']} total_tools={fed['total_tools']}")
    if fed["agents"] != 11 or fed["total_tools"] != 38:
        print(f"  {FAIL} 期望 11 agents / 38 tools")
        failures += 1

    # 2) 扁平清单
    resp = client.get("/mcp/federation/tools")
    assert resp.status_code == 200
    flat = resp.json()["tools"]
    print(f"{OK} GET /mcp/federation/tools -> {len(flat)} tools")
    if len(flat) != 38:
        print(f"  {FAIL} 期望 38 tools，实际 {len(flat)}")
        failures += 1

    # 3) 逐 Agent 调用代表工具
    reached_agents = set()
    for tool, args in CALLS:
        resp = client.post(f"/mcp/federation/{tool}/call", json={"arguments": args})
        agent = tool.split("__")[0]
        if resp.status_code == 200 and "result" in resp.json():
            reached_agents.add(agent)
            print(f"{OK} {tool} -> 200")
        else:
            print(f"{FAIL} {tool} -> {resp.status_code} {resp.text[:120]}")
            failures += 1

    # 4) 兼容性：旧版 /mcp/tools 仍是 6 工具
    resp = client.get("/mcp/tools")
    legacy = resp.json()["tools"]
    print(f"{OK} GET /mcp/tools (兼容) -> {len(legacy)} tools")
    if len(legacy) != 6:
        print(f"  {FAIL} 兼容契约破坏：期望 6，实际 {len(legacy)}")
        failures += 1

    # 5) 兼容性：旧版 get_bom 调用
    resp = client.post("/mcp/tools/get_bom/call", json={"arguments": {"bom_id": "BOM-NPI-007"}})
    if resp.status_code == 200 and resp.json()["result"].get("product_name"):
        print(f"{OK} POST /mcp/tools/get_bom/call -> 200")
    else:
        print(f"{FAIL} 旧版 get_bom 调用失败：{resp.status_code} {resp.text[:120]}")
        failures += 1

    # 6) 未知工具应 404
    resp = client.post("/mcp/federation/nope__missing/call", json={"arguments": {}})
    if resp.status_code == 404:
        print(f"{OK} 未知工具 -> 404 (符合预期)")
    else:
        print(f"{FAIL} 未知工具未返回 404：{resp.status_code}")
        failures += 1

    print("-" * 60)
    print(f"覆盖 Agent 数: {len(reached_agents)}/11  {sorted(reached_agents)}")
    if failures == 0:
        print(f"{OK} V1-2 能力层联邦验证全部通过")
        return 0
    print(f"{FAIL} 失败项：{failures}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
