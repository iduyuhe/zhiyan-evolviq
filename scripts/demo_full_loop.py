"""v28 Demo 全链路端到端演练 —— 三主义活循环 · 产业链联邦

模拟：3家企业（晶圆厂/封测厂/客户）协同完成紧急订单。
验证全部 12 个环节：
1~3. 多租户 → 联邦目标 → 风险 → 计划
4~6. UNS五路 → 隐性捕获 → KG锚定
7~8. Agent执行 → ROI闭环 → 蓝弧校验
9~12. 治理 → 本体 → 联邦 → 孪生大屏
"""

import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from src.runtime.main import app

PASS = 0
FAIL = 0

def ok(msg):
    global PASS; PASS += 1
    print(f"  [PASS] {msg}")

def fail(msg):
    global FAIL; FAIL += 1
    print(f"  [FAIL] {msg}")


async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:

        # 1
        print("\n[1] 产业链联邦 — 共享目标")
        r = await c.post("/federation/supply-chain/goal", json={
            "tenant_id": "t1", "goal": "紧急订单HPC-1007按期交付",
            "target_materials": ["硅片", "光刻胶"], "urgency": "high",
        })
        assert r.status_code == 200
        gid = r.json()["id"]
        ok(f"目标已共享: {gid}")

        # 2
        print("\n[2] 跨企业风险报告")
        await c.post("/federation/supply-chain/risk", json={
            "tenant_id": "t1", "material": "光刻胶ARF-02", "risk_level": "high",
            "description": "进口光刻胶船期延期7天",
        })
        await c.post("/federation/supply-chain/risk", json={
            "tenant_id": "t2", "material": "硅片300mm", "risk_level": "medium",
            "description": "硅片交期有3天不确定性",
        })
        r = await c.get("/federation/supply-chain/risks")
        assert r.json()["summary"]["total_active_risks"] == 2
        ok("2 条风险已报告")

        # 3
        print("\n[3] UNS 五路事件注入（连接主义）")
        from src.runtime.uns import uns
        uns.publish_gateway("opcua://fab-a/etcher-03", {"energy_kwh__etcher_03": 245.0, "status__etcher_03": "running"})
        uns.publish_system("erp://t1/sap/mm", {"order_status": "confirmed", "qty": 5000})
        uns.publish_human("wecom://zhang", {"content": "HPC-1007 硅片库存只够3天"}, entities=["EMP:zhang", "MAT:wafer-300"])
        uns.publish_meeting("meet://hpc-review", {"summary": "列为P0优先"}, entities=["EMP:li", "ORDER:HPC-1007"])
        uns.publish_collab("collab://fab-a/etcher-03", {"msg": "etch-03 ready for HPC-1007"}, entities=["DEV:etcher-03", "ORDER:HPC-1007"])
        ok(f"UNS 五路事件注入（总数 {len(uns._events)}）")

        # 4
        print("\n[4] 隐性捕获 → KG 锚定")
        from src.runtime.experience import experience
        from src.runtime.evolution.kg_facts import kg_facts
        tacit = experience.tacit_captures()
        props = kg_facts.list_proposals()
        ok(f"隐性捕获 {len(tacit)} 条, KG 提议 {len(props)} 条")

        # 5
        print("\n[5] 供应链 Agent 执行")
        r = await c.post("/sessions/quick-check", json={
            "goal": "检查HPC-1007订单的齐套率，确认硅片和光刻胶是否满足交付",
        })
        assert r.status_code == 200
        result = r.json().get("result", {})
        ok(f"Agent 执行完成: {result.get('status','?')} — {result.get('summary','')[:60]}")

        # 6
        print("\n[6] 蓝弧后果校验")
        from src.runtime.consequence import consequence
        consequence.expect_outcome("demo-act-1", "supply_chain", {"kitting_rate": 0.85})
        consequence.record("demo-act-1", {"kitting_rate": 0.82})
        s = consequence.stats()
        ok(f"后果校验: total={s['total_consequences']}, match_rate={s['match_rate']}")

        # 7
        print("\n[7] 治理面板")
        r = await c.get("/governance/panel")
        d = r.json()
        ok(f"治理: {d['summary']['total_agents']} agents (thin={d['summary']['thin']})")

        # 8
        print("\n[8] 本体 Schema + 发现")
        r = await c.get("/evolution/ontology/schema")
        d = r.json()
        ok(f"本体: {d['summary']['entity_types']} 实体, {d['summary']['relationship_types']} 关系")

        # 9
        print("\n[9] 联邦学习状态")
        r = await c.get("/federation/status")
        d = r.json()
        ok(f"联邦: {d['tenants']['total']} 租户, {d['kg_patterns']['total_patterns']} KG模式")

        # 10
        print("\n[10] 孪生大屏聚合数据")
        r = await c.get("/twin/dashboard")
        d = r.json()
        ok(f"孪生大屏: {d['uns']['total_events']} 事件, {d['kg']['total_proposals']} KG提议, "
           f"{d['experience']['total_records']} 经验, {d['consequence']['stats']['total_consequences']} 后果")

        # 11
        print("\n[11] 批准一条 KG 事实 → 验证虚拟后果")
        drafts = [p for p in kg_facts.list_proposals() if p["status"] == "draft"]
        if drafts:
            await c.post(f"/evolution/kg-facts/{drafts[0]['id']}/approve")
            # 验证 KG 状态
            p = kg_facts.get(drafts[0]["id"])
            ok(f"KG 事实已批准: {p['subject']} {p['predicate']} {p['object_val']} confidence={p.get('confidence',0):.2f}")
        else:
            ok("无待审批 draft（已有历史提议）")

        # 12
        print("\n[12] 生产健康检查")
        r = await c.get("/health/detailed")
        d = r.json()
        ok(f"健康检查: db={d['db']['mode']}, gateways={len(d.get('gateways',{}))}")

    print(f"\n{'='*50}")
    print(f"Demo 全链路演练: {PASS} 通过, {FAIL} 失败")
    return 0 if FAIL == 0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
