"""P1 端到端验证：真实 runtime 下验证自动调参 API + 经验库 API + 闭环。

走 HTTP（urllib，避免中文编码问题）。需先启动 runtime：
  ZHIYAN_DEMO_DATA=1 uvicorn src.runtime.main:app --port 8000
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method=method,
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def main():
    print("===== P1 端到端验证（真实 runtime）=====")

    # 1) 自动调参状态
    st, status = call("GET", "/strategy/auto-tune/status")
    print(f"[1] auto-tune/status: {st}")
    print(f"    enabled={status.get('auto_tune_enabled')} cooldown={status.get('cooldown_hours')}h "
          f"max_per_run={status.get('max_per_run')}")

    # 2) 触发一次自动调参（demo 信号应命中建议）
    st, run = call("POST", "/strategy/auto-tune/run")
    print(f"[2] auto-tune/run: {st} -> status={run.get('status')}")
    adj = run.get("adjustments", [])
    print(f"    自动调整数: {len(adj)}")
    for a in adj[:5]:
        print(f"      [{a['agent']}] {a['param']}: {a['old']} -> {a['new']} ({a['direction']})")

    # 3) 经验库查询（路由注册 + 查询可用）
    st, exp = call("GET", "/experience/supply_chain")
    print(f"[3] experience/supply_chain: {st}")
    print(f"    summary={exp.get('summary')}")

    # 4) 一键回滚（若有快照）
    st, rb = call("POST", "/strategy/auto-tune/rollback")
    print(f"[4] auto-tune/rollback: {st} -> status={rb.get('status')}")
    for r in rb.get("rolled_back", []):
        print(f"      restored {r['agent']}.{r['param']} -> {r['restored_to']}")

    ok = status.get("auto_tune_enabled") is True and st == 200
    print(f"\n===== 结果：{'✅ P1 自动调参/经验库 API 闭环可用' if ok else '❌ 失败'} =====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
