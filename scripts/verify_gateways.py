"""端到端验证 V1-3 工业协议网关：经真实 HTTP 应用验证四类网关。

用法：
    python scripts/verify_gateways.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from src.runtime.main import app  # noqa: E402

OK = "✅"
FAIL = "❌"


def main() -> int:
    client = TestClient(app)
    failures = 0

    # 1) 总览
    resp = client.get("/gateways")
    assert resp.status_code == 200, resp.text
    ov = resp.json()
    print(f"{OK} GET /gateways -> total={ov['total']} ready={ov['ready']} modes={ov['modes']}")
    if ov["total"] != 4 or ov["ready"] != 4:
        print(f"  {FAIL} 期望 4 类网关全部就绪")
        failures += 1

    # 2) 逐网关详情 + 读数
    checks = [
        ("opcua", {"address": "*", "count": 8}, "ns=2;s="),
        ("mqtt", {"address": "*", "count": 7}, "factory/"),
        ("modbus", {"address": "line_1_status", "count": 1}, "line_1"),
        ("ipc_cfx", {"address": "*", "count": 4}, "CFX."),
    ]
    for name, read_args, prefix in checks:
        detail = client.get(f"/gateways/{name}")
        if detail.status_code != 200:
            print(f"{FAIL} GET /gateways/{name} -> {detail.status_code}")
            failures += 1
            continue
        mode = detail.json().get("mode")
        rd = client.post(f"/gateways/{name}/read", json=read_args)
        if rd.status_code == 200 and rd.json()["count"] > 0 and rd.json()["points"][0]["tag"].startswith(prefix):
            print(f"{OK} {name} [{mode}] read -> {rd.json()['count']} 点（{rd.json()['points'][0]['tag']}）")
        else:
            print(f"{FAIL} {name} read -> {rd.status_code} {rd.text[:120]}")
            failures += 1

    # 3) 未知网关 404
    resp = client.get("/gateways/nope")
    if resp.status_code == 404:
        print(f"{OK} 未知网关 -> 404 (符合预期)")
    else:
        print(f"{FAIL} 未知网关未返回 404：{resp.status_code}")
        failures += 1

    print("-" * 60)
    if failures == 0:
        print(f"{OK} V1-3 工业协议网关验证全部通过（4 类网关就绪，模拟模式可运行）")
        return 0
    print(f"{FAIL} 失败项：{failures}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
