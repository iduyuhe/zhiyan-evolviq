"""性能对齐基准：进程内 ASGITransport 驱动真实 app，测四类指标。

指标：
1. 冷启动：import app + 初始化（manager/db/neo4j/kg/seed）耗时
2. 单线程延迟：各代表端点 warmup 5 次后跑 N 次，p50/p95/p99
3. 读并发：50 并发任务打 /kg/stats（重型聚合）
4. 写并发：20 并发 × 10 次真实 INSERT（POST /strategy/tune 追加审计路径），统计 ok/fail、wps、p95、database is locked 数

说明：本机无 PostgreSQL，db 回退 SQLite 文件（乐观基线，生产 PG 更快且并发更稳）。
结果落 bench_result.json。
"""
import asyncio
import json
import os
import time
import statistics

import httpx

# 让 /strategy 有演示数据（与 lifespan 同逻辑）
os.environ.setdefault("ZHIYAN_DEMO_DATA", "1")

from src.runtime.main import app  # noqa: E402


def pct(vals, p):
    if not vals:
        return 0.0
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


async def init_app():
    from src.gateways.manager import manager
    from src.common.db import init_db
    from src.common.neo4j_client import init_neo4j
    from src.runtime import knowledge_graph as kg
    await manager.ensure_ready()
    await init_db()
    await init_neo4j()
    try:
        await kg.build_from_seeds()
    except Exception as e:
        print(f"[warn] kg build skip: {e}")
    try:
        from src.runtime.core.demo_seed import seed_demo_data
        seed_demo_data()
    except Exception as e:
        print(f"[warn] demo seed skip: {e}")


async def measure_one(client, method, path, json_body=None):
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = await client.get(path)
        else:
            r = await client.post(path, json=json_body)
        dt = (time.perf_counter() - t0) * 1000.0
        return dt, r.status_code
    except Exception as e:
        return -1.0, f"ERR:{type(e).__name__}"


async def single_thread(client, endpoints, n=50):
    res = {}
    for ep in endpoints:
        method, path = ep["m"], ep["p"]
        # warmup
        for _ in range(5):
            await measure_one(client, method, path, ep.get("j"))
        samples = []
        for _ in range(n):
            dt, code = await measure_one(client, method, path, ep.get("j"))
            if dt >= 0:
                samples.append(dt)
        res[path] = {
            "n": len(samples),
            "p50": round(pct(samples, 50), 2),
            "p95": round(pct(samples, 95), 2),
            "p99": round(pct(samples, 99), 2),
            "mean": round(statistics.mean(samples), 2) if samples else 0,
        }
    return res


async def read_concurrency(client, path, tasks=50, iters=5):
    async def worker():
        s = []
        for _ in range(iters):
            dt, _ = await measure_one(client, "GET", path)
            if dt >= 0:
                s.append(dt)
        return s
    t0 = time.perf_counter()
    results = await asyncio.gather(*[worker() for _ in range(tasks)])
    wall = time.perf_counter() - t0
    allv = [v for sub in results for v in sub]
    return {
        "tasks": tasks, "iters": iters, "total": len(allv),
        "wall_s": round(wall, 2),
        "p95": round(pct(allv, 95), 2),
        "p99": round(pct(allv, 99), 2),
        "rps": round(len(allv) / wall, 1) if wall > 0 else 0,
    }


async def write_concurrency(client, path, json_body, tasks=20, iters=10):
    locked = 0
    ok = 0
    fail = 0
    samples = []

    async def worker(wid):
        nonlocal locked, ok, fail
        for i in range(iters):
            dt, code = await measure_one(
                client, "POST", path,
                {**json_body, "reason": f"bench-{wid}-{i}"},
            )
            if dt < 0:
                fail += 1
                continue
            samples.append(dt)
            if isinstance(code, str) and "ERR" in code:
                fail += 1
            elif code == 200:
                ok += 1
            else:
                fail += 1
                if code == 500:
                    locked += 1

    t0 = time.perf_counter()
    await asyncio.gather(*[worker(w) for w in range(tasks)])
    wall = time.perf_counter() - t0
    return {
        "tasks": tasks, "iters": iters,
        "ok": ok, "fail": fail, "locked_500": locked,
        "wps": round((ok + fail) / wall, 1) if wall > 0 else 0,
        "p95_ms": round(pct(samples, 95), 2),
        "max_ms": round(max(samples), 2) if samples else 0,
        "wall_s": round(wall, 2),
    }


async def main():
    t_import = time.perf_counter()
    # app 已在顶部 import；此处计初始化
    await init_app()
    cold = round((time.perf_counter() - t_import) * 1000.0, 1)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        read_eps = [
            {"m": "GET", "p": "/health"},
            {"m": "GET", "p": "/kg/stats"},
            {"m": "GET", "p": "/gateways"},
            {"m": "GET", "p": "/strategy"},
        ]
        print("▶ 单线程延迟 ...")
        single = await single_thread(client, read_eps, n=50)
        print("▶ 读并发 (50 tasks × 5) ...")
        rc = await read_concurrency(client, "/kg/stats", tasks=50, iters=5)
        print("▶ 写并发 (20 tasks × 10) ...")
        wc = await write_concurrency(
            client, "/strategy/tune",
            {"agent": "supply_chain", "param": "confidence_threshold", "value": 0.75},
            tasks=20, iters=10,
        )

    slo = {
        "冷启动 init_ms": {"实测": cold, "SLO建议": "<3000ms", "MET": cold < 3000},
        "/health p95_ms": {"实测": single["/health"]["p95"], "SLO建议": "<50ms", "MET": single["/health"]["p95"] < 50},
        "/kg/stats p95_ms": {"实测": single["/kg/stats"]["p95"], "SLO建议": "<120ms", "MET": single["/kg/stats"]["p95"] < 120},
        "读并发 rps": {"实测": rc["rps"], "SLO建议": ">200", "MET": rc["rps"] > 200},
        "写并发 wps": {"实测": wc["wps"], "SLO建议": ">50", "MET": wc["wps"] > 50},
        "写并发 locked_500": {"实测": wc["locked_500"], "SLO建议": "0", "MET": wc["locked_500"] == 0},
    }

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "env_note": "本机无 PG，db 回退 SQLite 文件（乐观基线；生产 PG 更快更稳）",
        "cold_start_init_ms": cold,
        "single_thread": single,
        "read_concurrency": rc,
        "write_concurrency": wc,
        "slo": slo,
    }
    with open("bench_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n===== 性能对齐 SLO 对照 =====")
    for k, v in slo.items():
        print(f"  {k:22s} 实测={v['实测']!s:>10}  SLO={v['SLO建议']:>8}  {'✅' if v['MET'] else '❌'}")
    print(f"\n结果已落 bench_result.json (冷启动={cold}ms)")


if __name__ == "__main__":
    asyncio.run(main())
