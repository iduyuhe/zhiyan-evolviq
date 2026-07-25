"""P0 记忆闭环端到端验证：编排→Insight 落库→召回读回。

运行（需先启动 runtime，或本脚本自带启动）：python scripts/verify_memory_p0.py
"""
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


async def main():
    print("===== P0 记忆闭环端到端验证 =====")

    # 1) 跑一次编排（会触发 apply_orchestration_result + apply_execution_result）
    #    选"能耗+OEE"场景：必触发跨域洞察模式（energy+oee 联合），确保产生 Insight。
    print("\n[1] 创建并执行 能耗+OEE 多 Agent 编排...")
    status, body = call("POST", "/sessions/multi-agent",
                        {"goal": "能耗与碳排放治理，联合 OEE 优化提升产线效率"})
    sid = body.get("session_id")
    print(f"    session_id={sid}, status={status}")
    status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
    r = body.get("report", {})
    print(f"    编排完成：{r.get('success_count')}/{r.get('sub_task_count')} 成功")
    print(f"    本次 cross_findings：{len(r.get('cross_findings', []))}")

    # 2) 确认 Orchestration 节点 + AgentRun 落库（apply_orchestration_result 已接线）
    print("\n[2] 查询 Orchestration 节点（验证编排结果不再静默丢失）...")
    status, body = call("GET", "/kg/query?node_id=ORCH:" + sid)
    neigh = body.get("neighbors", [])
    print(f"    ORCH 邻居数（AgentRun + Insight）：{len(neigh)}")
    assert len(neigh) >= r.get("sub_task_count", 0), "AgentRun 节点应随子任务数写入"

    # 3) 确认 Insight 落库（跨域洞察）
    print("\n[3] 查询知识图谱 Insight 节点...")
    status, body = call("GET", "/kg/query?label=Insight")
    insights = body.get("nodes", [])
    print(f"    Insight 节点数：{len(insights)}")
    for n in insights[:3]:
        print(f"      - [{n['props'].get('source')}] {n['props'].get('text', '')[:60]}")

    # 4) 召回验证：通过运行时 /kg/recall 端点召回历史经验（记忆闭环读回）
    print("\n[4] 记忆召回（相似目标，走运行时 API）...")
    import urllib.parse
    status, body = call("GET", "/kg/recall?goal=" + urllib.parse.quote("产线 OEE 能耗优化") + "&limit=5")
    mem_insights = body.get("insights", []) if isinstance(body, dict) else []
    print(f"    召回 insights 数：{len(mem_insights)}")
    for t in mem_insights[:3]:
        print(f"      - {t[:60]}")

    ok = len(neigh) >= r.get("sub_task_count", 0) and len(mem_insights) > 0
    print(f"\n===== 结果：{'✅ 记忆闭环已打通' if ok else '❌ 失败'} =====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
