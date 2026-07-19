"""知识图谱端到端验证（经真实 FastAPI 生命周期 /kg 接口）"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from src.runtime.main import app


def main():
    with TestClient(app) as client:
        r = client.get("/kg/stats")
        assert r.status_code == 200, r.text
        stats = r.json()
        print("📊 /kg/stats:", stats)
        assert stats["total_nodes"] > 0

        r = client.post("/kg/rebuild")
        assert r.status_code == 200, r.text
        print("🔄 /kg/rebuild 返回:", r.json())

        r = client.get("/kg/query?label=Material&category=三极管")
        assert r.status_code == 200
        print("🔍 Material(三极管) 节点数:", len(r.json().get("nodes", [])))

        r = client.get("/kg/query?node_id=CASE:CASE-2026-001&edge=怀疑设备")
        assert r.status_code == 200
        print("🔗 质量案例→设备 桥接:", [n["id"] for n in r.json().get("neighbors", [])])

        r = client.get("/kg/query?node_id=EQP:scanner_1&edge=有部件")
        assert r.status_code == 200
        print("⚙️ 设备→部件:", [n["id"] for n in r.json().get("neighbors", [])])
    print("\n✅ 知识图谱端到端验证通过")


if __name__ == "__main__":
    main()
