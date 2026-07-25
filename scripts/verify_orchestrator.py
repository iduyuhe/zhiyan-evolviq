"""多 Agent 编排端到端验证脚本（V1-5 缺口补齐）"""
import urllib.request
import json

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={'Content-Type': 'application/json'},
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')


def show_plan(body):
    p = body['plan']
    print(f"  source: {p['source']}, sub_tasks: {len(p['sub_tasks'])}")
    for st in p['sub_tasks']:
        print(f"    [{st['agent']:18s}] {st['sub_goal'][:50]}")


def show_report(body):
    r = body['report']
    print(f"  成功 {r['success_count']}/{r['sub_task_count']} (失败 {r['failed_count']})，耗时 {r['total_duration_ms']}ms")
    print(f"  关键指标: {r['key_metrics']}")
    if r['cross_findings']:
        print(f"  跨发现 ({len(r['cross_findings'])}):")
        for f in r['cross_findings'][:3]:
            print(f"    • {f[:100]}")
    if r['priority_actions']:
        print(f"  优先级动作 ({len(r['priority_actions'])}):")
        for p in r['priority_actions'][:3]:
            print(f"    [{p.get('source_agent', '?'):18s}] {p.get('detail', '')[:60]}")


print("===== 测试 1：NPI 5 Agent 编排 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "新产品导入评估"})
print(f"  创建: HTTP {status}")
show_plan(body)
sid = body['session_id']
status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
print(f"  执行: HTTP {status}")
show_report(body)

print()
print("===== 测试 2：客诉 5 Agent 编排 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "客户投诉某批次不良"})
print(f"  创建: HTTP {status}")
show_plan(body)
sid = body['session_id']
status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
print(f"  执行: HTTP {status}")
show_report(body)

print()
print("===== 测试 3：OEE 提升 5 Agent 编排 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "产线 OEE 太低怎么提升"})
print(f"  创建: HTTP {status}")
show_plan(body)
sid = body['session_id']
status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
print(f"  执行: HTTP {status}")
show_report(body)

print()
print("===== 测试 4：齐套率 5 Agent 编排 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "齐套率只有 60%，怎么提升"})
print(f"  创建: HTTP {status}")
show_plan(body)
sid = body['session_id']
status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
print(f"  执行: HTTP {status}")
show_report(body)

print()
print("===== 测试 5：能耗治理 4 Agent 编排 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "如何降低工厂碳排放"})
print(f"  创建: HTTP {status}")
show_plan(body)
sid = body['session_id']
status, body = call("POST", f"/sessions/{sid}/approve-multi", {"approved": True})
print(f"  执行: HTTP {status}")
show_report(body)

print()
print("===== 测试 6：关键词聚合兜底 =====")
status, body = call("POST", "/sessions/multi-agent", {"goal": "硅片库存和良率"})
print(f"  创建: HTTP {status}")
show_plan(body)
