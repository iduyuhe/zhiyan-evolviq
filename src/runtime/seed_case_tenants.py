"""研究案例租户开通（#429，2026-07-29 杜总破例授权）

背景：目前尚未真正开拓客户，但需要在生产系统里"以租户身份登录并看到研究案例推演数据"。
杜总定调：**企业入驻签约流程暂时先不走，直接先出来，这次先破例。**

因此本模块跳过 enterprise_onboarding 两阶段实例化（现状描述 → 凭证 → 接口实例化），
直接把两个研究案例（通讯 / 半导体）实例化为可登录租户。

🔴 红线仍然守住（破例的只是"流程"，不是"合规"）：
1. 匿名铁律：租户显示名一律匿名（某某通讯公司 / 某某半导体公司），
   `real_anchor`（中兴通讯 / 中芯国际）绝不写入租户名、账号名、画像或任何对外 payload。
2. 私域/公开边界：租户标记 `tenant_kind="research_case"`，数据来源标注"公开披露推演"，
   绝不冒充"已融合客户真实数据"，也绝不冒充已签约客户。
3. 北极星纪律：注入的决策信号一律 `real_time=False`（演示/推演态），
   不污染杜特第0号真实客户撑起的北极星真实率。

幂等：重复调用不重复建号、不重复累计信号。可经 ZHIYAN_CASE_TENANTS=0 关闭。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# 租户 ID 亦保持匿名语义（不用 zte / smic 等可反推真名的缩写）
CASE_TENANTS: list[dict] = [
    {
        "tenant_id": "telecom",
        "tenant_name": "某某通讯公司（研究案例租户·未签约）",
        "case_id": "case_telecom_2026",
        "industry": "通讯",
        "admin_user": "telecom_admin",
        "admin_display": "通讯研究案例管理员",
        "viewer_user": "telecom_viewer",
        "viewer_display": "通讯研究案例观察员",
        # 权限第③层：岗位（business_role）+ 行业模板键
        "permission_industry": "telecom_equipment",
        "admin_business_role": "plant_manager",     # 厂长视角：全量可见（含成本/驾驶舱）
        "viewer_business_role": "supply_manager",   # 供应链经理：看不到成本分析/财务驾驶舱
    },
    {
        "tenant_id": "semicon",
        "tenant_name": "某某半导体公司（研究案例租户·未签约）",
        "case_id": "case_semicon_2026",
        "industry": "半导体",
        "admin_user": "semicon_admin",
        "admin_display": "半导体研究案例管理员",
        "viewer_user": "semicon_viewer",
        "viewer_display": "半导体研究案例观察员",
        # 权限第③层：岗位（business_role）+ 行业模板键
        "permission_industry": "semiconductor_fab",
        "admin_business_role": "plant_manager",     # 厂长视角：全量可见
        "viewer_business_role": "device_engineer",  # 设备工程师：无成本类，但半导体模板额外可读良率
    },
]

# tenant_id → case_id 绑定（供 GET /cases/my 定位本租户所属研究案例）
TENANT_CASE_BINDING: dict[str, str] = {t["tenant_id"]: t["case_id"] for t in CASE_TENANTS}

SEED_PREFIX = "case-tenant-"


def default_password(username: str) -> str:
    """确定性初始密码（可经环境变量覆盖）。"""
    return (
        os.environ.get(f"ZHIYAN_CASE_PW_{username.upper()}", "")
        or os.environ.get("ZHIYAN_CASE_PW", "")
        or f"Zhiyan@{username}2026"
    )


def _scope_of(business_role: str | None, industry: str | None) -> dict | None:
    """按岗位 + 行业取权限模板库的标准作用域；取不到则 None（= 全放行，向后兼容）。"""
    if not business_role:
        return None
    try:
        from src.presets.permission_templates import scope_for_business_role

        return scope_for_business_role(business_role, industry=industry)
    except Exception as e:  # noqa: BLE001
        logger.warning("⚠️ 权限模板取用失败（降级为全放行）：%s/%s → %s", business_role, industry, e)
        return None


async def _apply_capability(username: str, business_role: str | None, scope: dict | None) -> bool:
    """给"已存在"的账号幂等补齐岗位作用域；已一致则跳过。失败绝不阻断启动。"""
    if not business_role:
        return False
    try:
        from src.runtime.authn.service import authn_service

        rec = await authn_service._load(username)
        if not rec:
            return False
        if rec.get("business_role") == business_role:
            return False
        await authn_service.set_capability(
            rec["id"], business_role=business_role, capability_scope=scope
        )
        logger.info("🔐 研究案例账号岗位已补齐：%s → %s", username, business_role)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("⚠️ 补齐岗位失败（不阻断启动）：%s → %s", username, e)
        return False


def _build_profile(spec: dict, case: dict | None) -> dict:
    """按研究案例生成租户企业画像（匿名；绝不写入 real_anchor）。"""
    interfaces = (case or {}).get("recommended_interfaces", [])
    return {
        "industry": spec["industry"],
        "region": "",
        "legal_entities": [],
        "org_scale": "1000+",
        "revenue_band": "",
        "systems": {
            "erp": "未声明（研究案例租户，尚未接内部数据源）",
            "mes": "未声明",
            "gateway": [],
            "social": [],
            "knowledge_base": False,
        },
        "intent": {
            "free_tier_ok": True,
            "internal_connect": "暂不",
            "concerns": "研究案例租户：仅基于公开披露推演，未接入任何企业内部真实数据。",
        },
        "narrative": (
            f"本租户为研究案例实例化租户（{spec['tenant_name']}），"
            f"绑定案例 {spec['case_id']}，全部数据来源于公开披露信息的推演，"
            f"非签约客户、非真实内部数据。推荐接口：{', '.join(interfaces) or '—'}。"
        ),
        "tenant_kind": "research_case",
        "bound_case_id": spec["case_id"],
        "data_origin": "public_disclosure_derivation",
    }


async def seed_case_tenants() -> dict:
    """开通研究案例租户 + 账号 + 画像 + 推演信号（幂等）。"""
    summary: dict = {"enabled": True, "tenants": []}
    if os.environ.get("ZHIYAN_CASE_TENANTS", "1") != "1":
        logger.info("⏭️ 研究案例租户未启用（ZHIYAN_CASE_TENANTS!=1），跳过")
        return {"enabled": False, "tenants": []}

    from src.runtime.authn.service import authn_service
    from src.runtime.tenant_store import tenant_store

    try:
        from src.agents.case_curator.agent import case_curator_agent

        case_curator_agent._ensure_seed()
    except Exception as e:  # noqa: BLE001
        logger.warning("⚠️ 案例库加载失败（研究案例租户仍继续开通）：%s", e)
        case_curator_agent = None  # type: ignore[assignment]

    for spec in CASE_TENANTS:
        tid = spec["tenant_id"]
        item: dict = {"tenant_id": tid, "case_id": spec["case_id"], "created": False, "accounts": []}

        if tenant_store.get(tid) is None:
            try:
                await tenant_store.register_with_id(tid, spec["tenant_name"])
                item["created"] = True
                logger.info("🏢 研究案例租户已开通：%s（%s）", tid, spec["tenant_name"])
            except Exception as e:  # noqa: BLE001
                logger.warning("⚠️ 研究案例租户开通失败（不阻断启动）：%s → %s", tid, e)
                summary["tenants"].append(item)
                continue
        else:
            logger.info("🏢 研究案例租户已存在（跳过）：%s", tid)

        industry = spec.get("permission_industry")
        for uname, role, disp, biz_role in (
            (spec["admin_user"], "tenant_admin", spec["admin_display"], spec.get("admin_business_role")),
            (spec["viewer_user"], "viewer", spec["viewer_display"], spec.get("viewer_business_role")),
        ):
            pw = default_password(uname)
            scope = _scope_of(biz_role, industry)
            try:
                await authn_service.create_user(
                    username=uname, password=pw, role=role,
                    tenant_id=tid, display_name=disp,
                    business_role=biz_role, capability_scope=scope,
                )
                item["accounts"].append(
                    {"username": uname, "role": role, "password": pw, "business_role": biz_role}
                )
                logger.info("👤 研究案例账号已建：%s（%s / 岗位 %s）", uname, role, biz_role or "未设")
            except ValueError:
                # 已存在：幂等补齐权限第③层岗位（生产上已建号的账号也能被"升级"）
                applied = await _apply_capability(uname, biz_role, scope)
                item["accounts"].append(
                    {
                        "username": uname, "role": role, "password": None,
                        "business_role": biz_role, "capability_backfilled": applied,
                    }
                )

        # 企业画像（匿名，标注研究案例来源）
        case = None
        if case_curator_agent is not None:
            try:
                case = case_curator_agent._get_case(spec["case_id"])
            except Exception:  # noqa: BLE001
                case = None
        try:
            from src.runtime.enterprise_store import profile_store

            if profile_store.get(tid) is None:
                profile_store.upsert(tid, _build_profile(spec, case))
                item["profile_seeded"] = True
        except Exception as e:  # noqa: BLE001
            logger.warning("⚠️ 研究案例租户画像写入失败：%s → %s", tid, e)

        # 推演决策信号（🔴 real_time=False，绝不计入北极星真实率）
        item["signals"] = _seed_case_signals(tid, case)
        summary["tenants"].append(item)

    return summary


def _seed_case_signals(tenant_id: str, case: dict | None) -> int:
    """把案例的 derived_insights 注入为租户级推演决策信号（演示态，幂等）。"""
    if not case:
        return 0
    try:
        from src.runtime.core.metrics import metrics
    except Exception:  # noqa: BLE001
        return 0
    prefix = f"{SEED_PREFIX}{tenant_id}-"
    try:
        if metrics.already_seeded(prefix):
            return 0
    except Exception:  # noqa: BLE001
        pass
    n = 0
    for i, ins in enumerate(case.get("derived_insights", [])):
        try:
            metrics.record_decision_realization(
                decision_id=f"{prefix}{i:03d}",
                realized=ins.get("value_judgment") == "high",
                real_time=False,  # 🔴 推演≠真实，绝不污染真实率
                tenant=tenant_id,
            )
            n += 1
        except Exception:  # noqa: BLE001
            break
    return n
