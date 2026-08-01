"""企业入驻 Agent——两阶段实例化框架的阶段二驱动入口（Phase 2，2026-07-29）

契约：docs/ENTERPRISE_PROFILE_SCHEMA.md。
职责：读取企业现状画像（声明式描述）→ 生成入驻画像摘要 →
     叠加案例库同行业 recommended_interfaces → 输出「建议开通 / 待补凭证 / 暂不需要」三态清单，
     并映射 §3.5 无感转型三圈解锁（外圈免费默认开；中圈/内圈按 intent 渐进）。

🔴 红线：
- 凭证只经 vault 引用（vault_id/kind），本 agent 输出**绝不含明文/密文**。
- 案例库 real_anchor（真实锚定公司）绝不进入本 agent 任何输出（匿名铁律）。
- legal_entities / narrative 属客户私域，仅在租户内可见，不进任何对外通道。
"""

from __future__ import annotations

import logging

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

# 接口 → 三圈映射（§3.5 无感转型三圈解锁）
_INTERFACE_CIRCLE = {
    # 外圈（免费，纯公开行业信号）
    "policy": "outer",
    "market": "outer",
    "benchmark": "outer",
    "disclosure": "outer",
    "industry_research": "outer",
    "executive_cockpit": "outer",
    "supply_chain": "outer",
    "compliance_q": "outer",
    # 中圈（付费线：接第 1 个内部数据源）
    "erp_writeback": "middle",
    "cost_analysis": "middle",
    # 内圈（私有化）
    "gateway_opcua": "inner",
    "social_wecom": "inner",
    "social_dingtalk": "inner",
    "email_imap": "inner",
}

# systems 已有项 → 可实例化的凭证 kind 映射
_SYSTEM_TO_CREDENTIAL = {
    "erp": "erp_writeback",
    "gateway_opcua": "gateway_opcua",
    "social_企业微信": "social_wecom",
    "social_钉钉": "social_dingtalk",
    "social_邮件": "email_imap",
}


class EnterpriseOnboardingAgent(BaseAgent):
    """企业入驻 Agent：现状画像 → 接口推荐三态清单 → 三圈解锁映射"""

    name = "enterprise_onboarding"
    description = "企业入驻：现状描述画像→案例库驱动接口推荐(建议开通/待补凭证/暂不需要)→三圈解锁引导"

    async def analyze(self, goal: str, tenant_id: str = "default", **kwargs) -> dict:
        from src.runtime.enterprise_store import profile_store, credential_vault

        profile = profile_store.get(tenant_id)
        if not profile:
            return {
                "status": "completed",
                "onboarding_stage": "not_started",
                "summary": (
                    "尚未录入企业现状描述。请先在「连接」页填写企业画像"
                    "（行业/区域/系统清单/接入意愿），系统将自动推荐该开通的集成接口。"
                ),
                "next_step": "POST /api/enterprise/profile 录入企业现状",
            }

        vault_refs = credential_vault.list_refs(tenant_id)
        recommendation = self._recommend(profile, vault_refs)
        portrait = self._portrait(profile)
        equipment = self._equipment_presets(profile.get("industry", ""))

        eq_tail = (
            f"该行业已预置 {equipment['profile_count']} 台 / {equipment['equipment_type_count']} 类设备模板，可直接匹配。"
            if equipment.get("matched")
            else "该行业暂无设备模板预设（可 1-2 天新建）。"
        )
        return {
            "status": "completed",
            "onboarding_stage": recommendation["stage"],
            "portrait": portrait,
            "recommendation": recommendation,
            "equipment_presets": equipment,  # #428：设备预设层接入对话式入驻路径
            "credential_refs": vault_refs,  # 仅引用元数据，无明文/密文
            "summary": (
                f"入驻画像已生成（行业：{profile.get('industry', '未知')}）。"
                f"建议开通 {len(recommendation['ready'])} 项、"
                f"待补凭证 {len(recommendation['pending_credentials'])} 项、"
                f"暂不需要 {len(recommendation['not_needed'])} 项。" + eq_tail
            ),
        }

    # ---------- 设备预设层接入（#428） ----------
    # 画像行业（中文枚举）→ 设备库行业代码
    _INDUSTRY_TO_EQUIPMENT: dict[str, str] = {
        "半导体": "semiconductor",
        "3C": "3c",
        "新能源汽车": "new_energy",
    }

    def _equipment_presets(self, industry: str) -> dict:
        """按画像行业拉取设备模板预设（客户接入时"选行业→自动匹配设备模板"）。"""
        code = self._INDUSTRY_TO_EQUIPMENT.get(industry)
        base = {"industry": industry, "industry_code": code, "matched": False,
                "equipment_type_count": 0, "profile_count": 0,
                "equipment_types": [], "equipments": []}
        if not code:
            base["note"] = "该行业暂无设备模板预设，接入时按 1-2 天新建模板流程处理"
            return base
        try:
            from src.agents.pm_maintenance import equipment_profiles

            overview = equipment_profiles.industry_overview().get(code, {})
            profiles = equipment_profiles.list_by_industry(code)
            base.update({
                "matched": True,
                "industry_cn": overview.get("industry_cn", industry),
                "equipment_type_count": overview.get("equipment_type_count", 0),
                "equipment_types": overview.get("equipment_types", []),
                "profile_count": len(profiles),
                "equipments": [
                    {
                        "equipment_id": p.equipment_id,
                        "name": p.name,
                        "type_cn": p.type_cn,
                        "vendor": p.vendor,
                        "model": p.model,
                        "opcua_tag_count": len(p.opcua_tags),
                        "mtbf_hours": p.mtbf_hours,
                    }
                    for p in profiles
                ],
                "note": "同型号直接套模板；不同型号按模板规则快速适配（数日而非数月）",
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"设备预设读取失败（不阻断入驻推荐）：{e}")
            base["note"] = "设备模板读取失败，可稍后重试"
        return base

    # ---------- 入驻画像摘要 ----------
    def _portrait(self, profile: dict) -> dict:
        """画像摘要（私域数据仅租户内可见；不含凭证）。"""
        systems = profile.get("systems", {}) or {}
        return {
            "industry": profile.get("industry", "其他"),
            "region": profile.get("region", ""),
            "org_scale": profile.get("org_scale", ""),
            "systems_summary": {
                "erp": systems.get("erp") or "无",
                "mes": systems.get("mes") or "无",
                "gateway": systems.get("gateway") or [],
                "social": systems.get("social") or [],
                "knowledge_base": bool(systems.get("knowledge_base")),
            },
            "internal_connect_intent": (profile.get("intent", {}) or {}).get("internal_connect", "暂不"),
            "updated_at": profile.get("updated_at", ""),
        }

    # ---------- 案例库驱动的接口推荐（D3） ----------
    def _case_interfaces(self, industry: str) -> list[str]:
        """查案例库同行业案例的 recommended_interfaces（匿名视图，绝不带 real_anchor）。"""
        try:
            from src.agents.case_curator.agent import case_curator_agent

            case_curator_agent._ensure_seed()
            cases = case_curator_agent._load()
            out: list[str] = []
            for c in cases:
                # 行业模糊匹配（"通讯" ⊂ "通讯设备 / 信息通信"）
                if industry and industry in c.get("industry", ""):
                    out.extend(c.get("recommended_interfaces", []))
            # 外圈公开信号接口始终纳入（免费预载活体）
            for base in ("policy", "market", "benchmark"):
                if base not in out:
                    out.append(base)
            return out
        except Exception as e:
            logger.warning(f"案例库读取失败，仅回退外圈基础接口：{e}")
            return ["policy", "market", "benchmark"]

    def _recommend(self, profile: dict, vault_refs: list[dict]) -> dict:
        """三态清单：建议开通(ready) / 待补凭证(pending_credentials) / 暂不需要(not_needed)。"""
        industry = profile.get("industry", "")
        systems = profile.get("systems", {}) or {}
        intent = (profile.get("intent", {}) or {}).get("internal_connect", "暂不")
        candidates = self._case_interfaces(industry)
        have_kinds = {r["kind"] for r in vault_refs}

        # 客户已有系统 → 可开的凭证类接口
        system_kinds: set[str] = set()
        if systems.get("erp") and systems.get("erp") != "无":
            system_kinds.add("erp_writeback")
        for g in systems.get("gateway") or []:
            if g == "OPC-UA":
                system_kinds.add("gateway_opcua")
        for s in systems.get("social") or []:
            k = _SYSTEM_TO_CREDENTIAL.get(f"social_{s}")
            if k:
                system_kinds.add(k)

        ready: list[dict] = []
        pending: list[dict] = []
        not_needed: list[dict] = []
        seen: set[str] = set()

        for iface in candidates + sorted(system_kinds):
            if iface in seen:
                continue
            seen.add(iface)
            circle = _INTERFACE_CIRCLE.get(iface, "outer")
            item = {"interface": iface, "circle": circle}
            if circle == "outer":
                # 外圈免费默认开（阶段一公开预载活体）
                ready.append(item)
            elif intent == "暂不":
                # 中圈/内圈：客户暂不接内部 → 暂不需要（不推销，价值驱动解锁）
                not_needed.append({**item, "reason": "客户意愿为「暂不」，遵循价值驱动解锁不推销"})
            elif iface in have_kinds:
                ready.append({**item, "note": "凭证已入 vault，可实例化"})
            elif iface in system_kinds or iface in ("erp_writeback", "cost_analysis"):
                pending.append({**item, "reason": "客户已具备对应系统，待提供凭证入 vault"})
            else:
                not_needed.append({**item, "reason": "客户现有系统清单中无对应系统"})

        stage = "instance_ready" if (intent != "暂不" and not pending) else (
            "awaiting_credentials" if pending else "free_tier_active"
        )
        return {
            "stage": stage,
            "ready": ready,
            "pending_credentials": pending,
            "not_needed": not_needed,
            "unlock_path": "外圈(免费公开信号)→中圈(接第1个内部数据源)→内圈(私有化)",
        }


enterprise_onboarding_agent = EnterpriseOnboardingAgent()
