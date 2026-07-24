"""质量合规 Agent 工具层——认证/审核/法规/CAPA 跟踪（确定性种子数据）

数据层：内置质量体系认证、内部审核、法规合规与纠正措施种子，可切换真实 QMS/GRC 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class ComplianceTools:
    """质量合规工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 质量/管理体系认证状态种子
    CERTIFICATIONS = [
        {"cert_id": "ISO9001", "name": "ISO 9001:2015 质量管理", "status": "valid",
         "issue": "2024-03", "expiry": "2027-03", "last_audit": "2026-01", "body": "SGS"},
        {"cert_id": "IATF16949", "name": "IATF 16949 汽车质量", "status": "valid",
         "issue": "2024-06", "expiry": "2027-06", "last_audit": "2026-03", "body": "TÜV"},
        {"cert_id": "ISO14001", "name": "ISO 14001:2015 环境管理", "status": "valid",
         "issue": "2024-09", "expiry": "2027-09", "last_audit": "2026-02", "body": "SGS"},
        {"cert_id": "ISO27001", "name": "ISO 27001 信息安全", "status": "in_progress",
         "issue": "", "expiry": "", "last_audit": "", "body": "TÜV",
         "target_date": "2026-12", "progress_pct": 65},
    ]

    # 内部/外部审核发现种子
    AUDITS = [
        {"finding_id": "F-001", "title": "校准标签过期", "source": "internal", "severity": "high",
         "due": "2026-08-15", "status": "open", "owner": "设备科"},
        {"finding_id": "F-002", "title": "温湿度记录缺失 3 批次", "source": "internal", "severity": "medium",
         "due": "2026-09-01", "status": "open", "owner": "生产科"},
        {"finding_id": "F-003", "title": "供应商审核报告缺漏 2 家", "source": "external", "severity": "low",
         "due": "2026-10-01", "status": "in_progress", "owner": "采购部"},
        {"finding_id": "F-004", "title": "ESD 防护定期检测未执行", "source": "customer", "severity": "high",
         "due": "2026-07-30", "status": "open", "owner": "工艺科"},
    ]

    # 法规合规状态种子
    REGULATIONS = [
        {"reg": "RoHS", "full_name": "有害物质限制指令", "status": "compliant",
         "last_review": "2026-01", "next_review": "2026-07", "risk": "low"},
        {"reg": "REACH", "full_name": "化学品注册评估许可", "status": "compliant",
         "last_review": "2026-02", "next_review": "2026-08", "risk": "low"},
        {"reg": "Conflict Minerals", "full_name": "冲突矿产报告", "status": "pending",
         "last_review": "2025-12", "next_review": "2026-05-31", "risk": "medium"},
        {"reg": "WEEE", "full_name": "废弃电子电气设备指令", "status": "compliant",
         "last_review": "2025-11", "next_review": "2026-11", "risk": "low"},
    ]

    async def get_certifications(self) -> list[dict]:
        out = []
        for c in self.CERTIFICATIONS:
            item = {
                "cert_id": c["cert_id"], "name": c["name"], "status": c["status"],
                "body": c.get("body", ""),
            }
            if c["status"] == "valid":
                item["issue"] = c["issue"]
                item["expiry"] = c["expiry"]
                item["last_audit"] = c["last_audit"]
            else:
                item["target_date"] = c.get("target_date", "")
                item["progress_pct"] = c.get("progress_pct", 0)
            out.append(item)
        return out

    async def get_audit_findings(self) -> list[dict]:
        return self.AUDITS[:]

    async def get_regulatory_summary(self) -> list[dict]:
        return self.REGULATIONS[:]

    async def create_capa(self, finding_id: str, title: str) -> dict:
        """授权内行动：对审核发现生成纠正预防措施（CAPA）。"""
        return {
            "task_id": f"CAPA-{finding_id}",
            "finding_id": finding_id,
            "title": title,
            "note": "已生成 CAPA 任务（授权内自动）",
        }

    async def get_compliance_summary(self) -> dict:
        """全厂合规概览（汇总统计）。"""
        certs = await self.get_certifications()
        audits = await self.get_audit_findings()
        regs = await self.get_regulatory_summary()

        valid_certs = sum(1 for c in certs if c["status"] == "valid")
        in_progress_certs = sum(1 for c in certs if c["status"] == "in_progress")
        open_findings = sum(1 for a in audits if a["status"] == "open")
        critical_findings = sum(1 for a in audits if a["status"] == "open" and a["severity"] == "high")
        reg_compliant = sum(1 for r in regs if r["status"] == "compliant")

        return {
            "valid_certs": valid_certs,
            "in_progress_certs": in_progress_certs,
            "total_audit_findings": len(audits),
            "open_findings": open_findings,
            "critical_findings": critical_findings,
            "total_regulations": len(regs),
            "compliant_regs": reg_compliant,
        }
