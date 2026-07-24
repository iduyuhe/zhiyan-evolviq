"""采购与供应商管理 Agent 工具层——供应商绩效、合同、竞价（确定性种子数据）

数据层：内置供应商评分、合同状态与采购策略种子，可切换真实 SRM/ERP 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class ProcurementTools:
    """采购与供应商管理工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # 供应商绩效种子（百分制，越高越好）
    SUPPLIERS = [
        {"id": "S-WAF", "name": "华芯半导体", "category": "晶圆", "score": 88,
         "delivery": 92, "quality": 90, "cost": 82, "compliance": 95, "status": "active",
         "contract_end": "2027-06", "tier": "A"},
        {"id": "S-CHEM", "name": "巨化化工", "category": "电子化学品", "score": 76,
         "delivery": 70, "quality": 80, "cost": 78, "compliance": 90, "status": "active",
         "contract_end": "2026-09", "tier": "B"},
        {"id": "S-PKG", "name": "华天封装", "category": "封装测试", "score": 82,
         "delivery": 85, "quality": 88, "cost": 76, "compliance": 92, "status": "active",
         "contract_end": "2027-03", "tier": "A"},
        {"id": "S-EQP", "name": "中微设备", "category": "设备备件", "score": 65,
         "delivery": 60, "quality": 70, "cost": 65, "compliance": 75, "status": "probation",
         "contract_end": "2026-12", "tier": "C", "risk_note": "交期不稳，需重点监控"},
    ]

    # 采购合同种子（万元）
    CONTRACTS = [
        {"id": "CT-001", "supplier": "华芯半导体", "value_wan": 8000,
         "start": "2025-07", "end": "2027-06", "status": "active", "auto_renew": True},
        {"id": "CT-002", "supplier": "巨化化工", "value_wan": 2000,
         "start": "2025-10", "end": "2026-09", "status": "active", "auto_renew": False},
        {"id": "CT-003", "supplier": "中微设备", "value_wan": 1200,
         "start": "2025-12", "end": "2026-12", "status": "active", "auto_renew": False},
    ]

    # 采购策略项
    STRATEGY_ITEMS = [
        {"focus": "国产替代推进", "progress_pct": 70, "priority": "high", "note": "光刻胶国产化认证中"},
        {"focus": "长协降本谈判", "progress_pct": 40, "priority": "medium", "note": "晶圆产能长约谈判中"},
        {"focus": "供应商淘汰", "progress_pct": 20, "priority": "low", "note": "低分供应商评估流程启动"},
    ]

    async def get_suppliers(self) -> list[dict]:
        return self.SUPPLIERS[:]

    async def get_contracts(self) -> list[dict]:
        return self.CONTRACTS[:]

    async def get_strategy_items(self) -> list[dict]:
        return self.STRATEGY_ITEMS[:]

    async def create_supplier_review(self, supplier_id: str, reason: str) -> dict:
        """授权内行动：对低绩效供应商生成评审任务。"""
        return {
            "task_id": f"REV-{supplier_id}",
            "supplier_id": supplier_id,
            "reason": reason,
            "note": "已生成供应商评审任务（授权内自动）",
        }
