"""Phase 2 企业入驻实例化 —— 两阶段实例化框架产品化测试（2026-07-29）

覆盖：
1. 注册表含 enterprise_onboarding（第 23 个 agent）
2. route_goal("企业入驻现状描述") → enterprise_onboarding
3. 无画像时 onboarding_stage = not_started
4. 录入画像后生成三态推荐（建议开通 / 待补凭证 / 暂不需要）
5. CredentialVault 加密后仅回 vault_id 引用（明文不落库 / 不进响应）
6. 跨租户 reveal 返回 None（租户隔离）
7. enterprise_onboarding 输出零真实锚定名外泄（匿名铁律）
8. API 端点冒烟（profile/credentials/recommendations，fail-closed 验证）

范围纪律：只做通讯单案例起步；real_anchor 仅 case_curator 内部变量，绝不外泄。
"""

import json
import os
import uuid

import pytest

# 🔴 必须在 import enterprise_store（经 router 间接 import）之前设置，
# 否则 _DATA_DIR 已在模块加载时捕获为 data/，凭证会落到生产态并跨用例累积。
_TMP = "/tmp/zhiyan_enterprise_test"
os.environ["ZHIYAN_ENTERPRISE_DATA_DIR"] = _TMP

from src.runtime.agent.router import AGENT_REGISTRY, route_goal

# 🔴 匿名铁律：真实锚定名片段，任何形式的外部结果都不得含
LEAK_TOKENS = ["中兴", "000063", "ZTE", "zte"]


def _assert_no_leak(result, where: str):
    blob = json.dumps(result, ensure_ascii=False, default=str)
    for tok in LEAK_TOKENS:
        assert tok not in blob, f"❌ {where} 外泄真实锚定名片段 {tok!r}"


_TMP_ARTIFACTS = ("enterprise_profiles.json", "credential_vault.json", "vault.key")


def _purge_tmp_artifacts(target_dir: str):
    """尽力清理产物文件，**绝不做目录级 rmtree**，且失败不阻断。

    隔离性由「每个用例一个全新子目录」保证，本函数只是顺手回收磁盘。
    受控/沙箱环境常拦截删除（回收站不可用 fail-closed、批量删除阈值保护），
    目录级删除被拦时甚至会抛 SystemExit 打断整个测试会话——那是环境噪音，
    不该伪装成业务回归，所以这里连 BaseException 一起吞掉。
    """
    for fname in _TMP_ARTIFACTS:
        fp = os.path.join(target_dir, fname)
        if os.path.exists(fp):
            try:
                os.remove(fp)
            except BaseException:  # noqa: BLE001
                pass


@pytest.fixture(autouse=True)
def _isolate_store():
    """每个用例分配**全新的独立目录** + 重置进程级单例。

    单例重置后，同步给已加载的 API 模块（enterprise.py 静态 import 了单例），
    保证 API 端点也指向新的隔离实例。显式传 path，不依赖 _DATA_DIR
    在模块导入期是否已被捕获。

    隔离策略（2026-08-01 改）：过去靠「每次删空同一个 tmp 目录」实现隔离，
    在拦截删除的受控环境里会退化成用例间互相污染甚至打断会话。
    现在改为每个用例一个唯一子目录——隔离不再依赖删除是否成功。
    """
    case_dir = os.path.join(_TMP, uuid.uuid4().hex[:12])
    os.makedirs(case_dir, exist_ok=True)
    os.environ["ZHIYAN_ENTERPRISE_DATA_DIR"] = case_dir

    from src.runtime import enterprise_store

    enterprise_store._DATA_DIR = case_dir  # 覆盖模块级常量，兜底
    enterprise_store.profile_store = enterprise_store.EnterpriseProfileStore(
        path=os.path.join(case_dir, "enterprise_profiles.json")
    )
    enterprise_store.credential_vault = enterprise_store.CredentialVault(
        path=os.path.join(case_dir, "credential_vault.json"),
        key_path=os.path.join(case_dir, "vault.key"),
    )
    try:
        import src.runtime.api.enterprise as ent

        ent.profile_store = enterprise_store.profile_store
        ent.credential_vault = enterprise_store.credential_vault
    except ImportError:
        pass
    yield
    _purge_tmp_artifacts(case_dir)


# ===== 1. 注册表 + 路由 =====

def test_registry_has_enterprise_onboarding():
    assert "enterprise_onboarding" in AGENT_REGISTRY, "注册表须含 enterprise_onboarding"
    assert len(AGENT_REGISTRY) == 24


def test_route_goal_triggers_enterprise_onboarding():
    assert route_goal("请做企业入驻现状描述与接口推荐") == "enterprise_onboarding"
    assert route_goal("我要开通接口，先录入企业画像") == "enterprise_onboarding"
    assert route_goal("onboarding 入驻推荐") == "enterprise_onboarding"


# ===== 2. 无画像 / 入驻前 =====

@pytest.mark.asyncio
async def test_not_started_when_no_profile():
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent

    res = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id="tenant_alpha")
    assert res["status"] == "completed"
    assert res["onboarding_stage"] == "not_started"
    _assert_no_leak(res, "enterprise_onboarding.not_started")
    # 不携带任何画像/推荐结构（未录入前）
    assert "recommendation" not in res


# ===== 3. 录入画像 → 三态推荐 =====

@pytest.mark.asyncio
async def test_profile_then_three_state_recommendation():
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent
    from src.runtime.enterprise_store import profile_store

    tid = "tenant_beta"
    profile = {
        "industry": "通讯",
        "region": "深圳",
        "org_scale": "1000+",
        "systems": {
            "erp": "SAP",
            "mes": "自研",
            "gateway": ["OPC-UA"],
            "social": ["企业微信"],
            "knowledge_base": True,
        },
        "intent": {"free_tier_ok": True, "internal_connect": "评估后", "concerns": ""},
        "narrative": "典型通讯设备制造商，多基地生产。",
    }
    profile_store.upsert(tid, profile)

    res = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    assert res["status"] == "completed"
    assert res["onboarding_stage"] in ("free_tier_active", "awaiting_credentials", "instance_ready")

    rec = res["recommendation"]
    # 三态清单结构齐备
    assert set(rec.keys()) >= {"stage", "ready", "pending_credentials", "not_needed", "unlock_path"}
    # 外圈公开信号至少含 policy/market/benchmark
    ready_ifaces = {r["interface"] for r in rec["ready"]}
    assert {"policy", "market", "benchmark"} <= ready_ifaces
    # 客户具备系统 → 待补凭证或已开通（中圈/内圈）
    pending_or_ready = {r["interface"] for r in rec["ready"] + rec["pending_credentials"]}
    assert "erp_writeback" in pending_or_ready  # SAP 已填 → 应进入待补凭证（凭证未入）
    assert "gateway_opcua" in pending_or_ready  # OPC-UA 已填
    assert "social_wecom" in pending_or_ready   # 企业微信已填

    # 🔴 匿名铁律：输出零真名
    _assert_no_leak(res, "enterprise_onboarding.recommendation")
    # 画像摘要不带入凭证明文
    assert "credentials" not in res["portrait"]
    # 凭证引用仅元数据
    assert res["credential_refs"] == []


@pytest.mark.asyncio
async def test_intent_now_open_moves_to_pending_or_ready():
    """intent=现在就开 且系统已具备 → 进入 pending_credentials（凭证未入 vault）。"""
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent
    from src.runtime.enterprise_store import profile_store

    tid = "tenant_gamma"
    profile = {
        "industry": "通讯",
        "systems": {"erp": "SAP", "gateway": ["OPC-UA"], "social": []},
        "intent": {"internal_connect": "现在就开"},
    }
    profile_store.upsert(tid, profile)
    res = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    rec = res["recommendation"]
    assert rec["stage"] in ("awaiting_credentials", "instance_ready")
    pending_ifaces = {r["interface"] for r in rec["pending_credentials"]}
    assert "erp_writeback" in pending_ifaces
    _assert_no_leak(res, "enterprise_onboarding.intent_now")


# ===== 4. 凭证 Vault 加密 + 租户隔离 =====

def test_vault_store_returns_only_ref_and_encrypts():
    from src.runtime.enterprise_store import credential_vault

    ref = credential_vault.store("tenant_delta", "erp_writeback", {"url": "x", "user": "u", "pwd": "s3cr3t"})
    # 返回引用不含明文/密文
    assert set(ref.keys()) == {"vault_id", "kind", "tenant_id"}
    assert ref["kind"] == "erp_writeback"
    assert ref["tenant_id"] == "tenant_delta"
    # 落盘记录为密文（vault_id 指向 cipher）
    import json as _json

    with open(credential_vault.path, "r", encoding="utf-8") as f:
        raw = _json.load(f)
    rec = raw[ref["vault_id"]]
    assert rec["cipher"] != "s3cr3t"  # 明文已加密
    assert "s3cr3t" not in rec["cipher"]  # 密文非明文裸串
    assert rec["tenant_id"] == "tenant_delta"


def test_vault_reveal_tenant_isolation():
    """跨租户 reveal 返回 None（租户隔离）；同租户可还原明文。"""
    from src.runtime.enterprise_store import credential_vault

    ref = credential_vault.store("tenant_echo", "social_wecom", {"corp_id": "C1", "secret": "K2"})
    # 同租户可 reveal
    plain = credential_vault.reveal(ref["vault_id"], "tenant_echo")
    assert plain is not None
    assert "K2" in plain
    # 跨租户静默拒绝
    assert credential_vault.reveal(ref["vault_id"], "tenant_foxtrot") is None
    # 不存在的 vault_id
    assert credential_vault.reveal("nonexistent", "tenant_echo") is None


def test_vault_list_refs_no_plaintext():
    from src.runtime.enterprise_store import credential_vault

    credential_vault.store("tenant_hotel", "email_imap", {"host": "h", "pwd": "p"})
    refs = credential_vault.list_refs("tenant_hotel")
    assert len(refs) == 1
    assert set(refs[0].keys()) == {"vault_id", "kind", "created_at"}
    # 跨租户不可见
    assert credential_vault.list_refs("tenant_india") == []


def test_vault_delete_cross_tenant_silent():
    from src.runtime.enterprise_store import credential_vault

    ref = credential_vault.store("tenant_juliet", "gateway_opcua", {"endpoint": "opc.tcp://x"})
    # 跨租户删除失败（返回 False，不抛错）
    assert credential_vault.delete(ref["vault_id"], "tenant_kilo") is False
    # 同租户删除成功
    assert credential_vault.delete(ref["vault_id"], "tenant_juliet") is True
    assert credential_vault.reveal(ref["vault_id"], "tenant_juliet") is None


def test_vault_fail_closed_without_fernet(monkeypatch):
    """加密不可用（fernet=None）时 store 抛 RuntimeError，绝不明文落库。"""
    from src.runtime import enterprise_store

    v = enterprise_store.CredentialVault()
    monkeypatch.setattr(v, "_fernet", None)
    with pytest.raises(RuntimeError):
        v.store("tenant_lima", "erp_writeback", {"pwd": "x"})


# ===== 5. 凭证入 vault 后推荐升级为 ready =====

@pytest.mark.asyncio
async def test_credential_stored_moves_pending_to_ready():
    from src.agents.enterprise_onboarding.agent import enterprise_onboarding_agent
    from src.runtime.enterprise_store import credential_vault, profile_store

    tid = "tenant_mike"
    profile_store.upsert(tid, {
        "industry": "通讯",
        "systems": {"erp": "SAP"},
        "intent": {"internal_connect": "现在就开"},
    })
    # 先推荐：erp_writeback 待补凭证
    before = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    assert any(r["interface"] == "erp_writeback" for r in before["recommendation"]["pending_credentials"])

    # 入 vault 凭证
    credential_vault.store(tid, "erp_writeback", {"url": "x", "user": "u", "pwd": "p"})

    # 后推荐：erp_writeback 升级为 ready（凭证已入）
    after = await enterprise_onboarding_agent.analyze("入驻推荐", tenant_id=tid)
    assert any(r["interface"] == "erp_writeback" and r.get("note") for r in after["recommendation"]["ready"])
    _assert_no_leak(after, "enterprise_onboarding.after_credential")


# ===== 6. API 端点冒烟（含 fail-closed） =====

@pytest.mark.asyncio
async def test_api_profile_and_credentials_flow():
    """profile 录入 → credentials 入 vault（仅回引用）→ recommendations 三态。"""
    from httpx import ASGITransport, AsyncClient

    import sys

    sys.path.insert(0, ".")
    from src.runtime.main import app
    from src.runtime.authn.security import encode_jwt

    token = encode_jwt({"sub": "svc", "role": "OPERATOR", "tenant_id": "tenant_november"})
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # 录入画像
        r = await c.post("/enterprise/profile", headers=headers, json={
            "industry": "通讯",
            "region": "深圳",
            "org_scale": "1000+",
            "systems": {"erp": "SAP", "gateway": ["OPC-UA"], "social": ["企业微信"]},
            "intent": {"internal_connect": "现在就开"},
        })
        assert r.status_code == 200, r.text
        # 取回画像：无凭证明文
        r2 = await c.get("/enterprise/profile", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["exists"] is True
        blob = json.dumps(r2.json(), ensure_ascii=False)
        assert "pwd" not in blob and "secret" not in blob

        # 入 vault 凭证：仅回引用
        r3 = await c.post("/enterprise/credentials", headers=headers, json={
            "kind": "erp_writeback",
            "secret": {"url": "x", "user": "u", "pwd": "SUPER_SECRET"},
        })
        assert r3.status_code == 200, r3.text
        ref = r3.json()["ref"]
        assert "vault_id" in ref and "erp_writeback" == ref["kind"]
        # 🔴 响应绝不回显明文
        assert "SUPER_SECRET" not in r3.text

        # 列表：仅元数据
        r4 = await c.get("/enterprise/credentials", headers=headers)
        assert r4.status_code == 200
        assert r4.json()["total"] == 1
        assert "SUPER_SECRET" not in r4.text

        # 推荐三态
        r5 = await c.get("/enterprise/recommendations", headers=headers)
        assert r5.status_code == 200, r5.text
        rec = r5.json()["recommendation"]
        ready_ifaces = {x["interface"] for x in rec["ready"]}
        assert "erp_writeback" in ready_ifaces  # 凭证已入 → ready
        # 零泄漏
        _assert_no_leak(r5.json(), "api.recommendations")


@pytest.mark.asyncio
async def test_api_cross_tenant_credential_invisible():
    """租户 A 的凭证，租户 B 列表/删除均不可见。"""
    from httpx import ASGITransport, AsyncClient

    import sys

    sys.path.insert(0, ".")
    from src.runtime.main import app
    from src.runtime.authn.security import encode_jwt

    tA = encode_jwt({"sub": "svc", "role": "OPERATOR", "tenant_id": "tenant_oscar"})
    tB = encode_jwt({"sub": "svc", "role": "OPERATOR", "tenant_id": "tenant_papa"})
    hA = {"Authorization": f"Bearer {tA}"}
    hB = {"Authorization": f"Bearer {tB}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # A 入凭证
        ra = await c.post("/enterprise/credentials", headers=hA, json={
            "kind": "email_imap", "secret": {"pwd": "A_SECRET"}
        })
        assert ra.status_code == 200
        vid = ra.json()["ref"]["vault_id"]
        # B 列表看不到
        rb = await c.get("/enterprise/credentials", headers=hB)
        assert rb.json()["total"] == 0
        # B 删除 A 的凭证 → 404
        rd = await c.delete(f"/enterprise/credentials/{vid}", headers=hB)
        assert rd.status_code == 404


@pytest.mark.asyncio
async def test_api_fail_closed_returns_503_without_fernet(monkeypatch):
    """vault 加密组件失效时，凭证入 vault 端点回 503（fail-closed）。"""
    import sys

    sys.path.insert(0, ".")
    from httpx import ASGITransport, AsyncClient

    from src.runtime import enterprise_store
    from src.runtime.main import app
    from src.runtime.authn.security import encode_jwt

    monkeypatch.setattr(enterprise_store.credential_vault, "_fernet", None)

    token = encode_jwt({"sub": "svc", "role": "OPERATOR", "tenant_id": "tenant_quebec"})
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/enterprise/credentials", headers=headers, json={
            "kind": "erp_writeback", "secret": {"pwd": "x"}
        })
        assert r.status_code == 503, r.text
