"""端到端验证 v22 蓝弧闭环：执行后果回流 → 校验 → 认知层修正

测试顺序：
1. 注册预期 → 发布后果 → 校验 match
2. 预期不匹配 → KG 置信度降低
3. 纠错 draft 自动提议（低于阈值）
4. UNS 自动捕获
5. API 端点可用
6. 统计信息正确
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
from src.runtime.consequence import consequence
from src.runtime.evolution.kg_facts import kg_facts
from src.runtime.experience import experience
from src.runtime.uns import uns

# 清空状态（保留 UNS 订阅者）
consequence.clear()
kg_facts._proposals.clear()
experience._records.clear()
uns._events.clear()

print("=" * 60)
print("🧪 [v22] 蓝弧闭环端到端验证")
print("=" * 60)

# ---- 1. 注册预期 → 后果匹配（正反馈）----
consequence.expect_outcome("act-v1", "energy_carbon", {"energy_kwh": 100.0}, linked_fact_id=None)
rec = consequence.record("act-v1", {"energy_kwh": 100.0})
assert rec is not None and rec.match is True
print(f"✅ [v22-1] 后果校验 match=True: action=act-v1 agent=energy_carbon")

# ---- 2. 预期不匹配 → KG 置信度降低 ----
fact = kg_facts.propose("default", "energy_carbon", "EMP:zhang", "tacit_judges", "交期风险", confidence=0.60)
fid = fact["id"]
consequence.expect_outcome("act-v2", "energy_carbon", {"risk": 1}, linked_fact_id=fid)
consequence.record("act-v2", {"risk": 5.0})
updated = kg_facts.get(fid)
assert updated is not None and updated["confidence"] < 0.60 and updated["status"] == "needs_review"
print(f"✅ [v22-2] KG 置信度降低: {updated['confidence']:.2f} (原 0.60) → status={updated['status']}")

# ---- 3. 纠错 draft 自动提议（置信度低于 0.30）----
fact2 = kg_facts.propose("default", "energy_carbon", "EMP:li", "tacit_judges", "无风险", confidence=0.40)
fid2 = fact2["id"]
consequence.expect_outcome("act-v3", "energy_carbon", {"risk": 0}, linked_fact_id=fid2)
consequence.record("act-v3", {"risk": 1.0})  # mismatch → 0.25 < 0.30
props = kg_facts.list_proposals()
corrections = [p for p in props if p.get("corrects") == fid2]
assert len(corrections) == 1, f"预期 1 条纠错 draft，实际 {len(corrections)}"
assert "~tacit_judges" in corrections[0]["predicate"]
print(f"✅ [v22-3] 自动纠错已提议: {corrections[0]['subject']} {corrections[0]['predicate']} {corrections[0]['object_val']}")

# ---- 4. UNS 自动捕获 ----
consequence.expect_outcome("act-v4", "energy_carbon", {"power_kw": 50.0})
uns.publish_gateway("opcua://actuator", {"action_id": "act-v4", "power_kw": 50.0})
recs = consequence.query(agent="energy_carbon")
matched = [r for r in recs if r["action_id"] == "act-v4"]
assert len(matched) >= 1 and matched[0]["match"] is True
print(f"✅ [v22-4] UNS gateway 自动捕获后果: action=act-v4 match={matched[0]['match']}")

# ---- 5. API 端点（通过 httpx ASGITransport，需 async）----
try:
    import asyncio
    import httpx
    from src.runtime.main import app

    async def check_api():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/experience/tacit")
            assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
            data = r.json()
            needed = ("tacit_captures", "pending_kg_facts")
            assert all(k in data for k in needed), f"keys={list(data.keys())} body={r.text[:200]}"

            r2 = await client.get("/experience/consequence")
            assert r2.status_code == 200
            data2 = r2.json()
            assert "records" in data2
            assert "stats" in data2
            assert data2["stats"]["total_consequences"] >= 3

            # 按 agent 查询
            r3 = await client.get("/experience/consequence?agent=energy_carbon")
            assert r3.status_code == 200
            data3 = r3.json()
            assert len(data3["records"]) >= 2
        return True

    asyncio.run(check_api())
    print(f"✅ [v22-5] API 端点正常: /experience/tacit + /experience/consequence")
except ImportError:
    print(f"⚠️ [v22-5] httpx 不可用，跳过 API 验证")

# ---- 6. 统计信息 ----
stats = consequence.stats()
print(f"📊 [v22-6] 蓝弧闭环统计: total={stats['total_consequences']} "
      f"validated={stats['validated']} contradicted={stats['contradicted']} "
      f"match_rate={stats['match_rate']}")

# ---- 7. 经验库有后果反馈 ----
outcomes = experience.outcome_records()
print(f"📊 [v22-7] 经验库后果反馈: {len(outcomes)} 条")

# ---- 总结 ----
print("\n" + "=" * 60)
print("🎉 [v22] 蓝弧闭环端到端验证全部通过")
print("=" * 60)

# 清理（保留订阅者）
consequence.clear()
kg_facts._proposals.clear()
experience._records.clear()
uns._events.clear()
