"""研发新产导入 Agent 工具层——NPI 项目全生命周期、里程碑、批量试产（确定性种子数据）

数据层：内置 NPI 项目与里程碑种子，可切换真实 PLM/PMS 系统。
全部数字由种子 + 确定性规则推导（事实锚点），不含任何 LLM 推算。
"""

from __future__ import annotations


class NpiTools:
    """研发新产导入工具集（in-process，供 Agent 与 MCP 联邦共用）。"""

    # NPI 项目种子；stage=概念/设计/原型/小批量/量产
    PROJECTS = [
        {"id": "NPI-001", "name": "28nm 逻辑芯片 v2.0", "stage": "pilot",
         "on_schedule": True, "milestone_pct": 80, "risk": "low",
         "owner": "张工", "eta": "2026-Q3"},
        {"id": "NPI-002", "name": "功率器件 Gen3", "stage": "prototype",
         "on_schedule": True, "milestone_pct": 55, "risk": "low",
         "owner": "李工", "eta": "2026-Q4"},
        {"id": "NPI-003", "name": "BMS 控制器 R3", "stage": "design",
         "on_schedule": False, "milestone_pct": 30, "risk": "high",
         "owner": "王工", "eta": "2027-Q1", "risk_note": "关键芯片选型延迟 6 周"},
        {"id": "NPI-004", "name": "先进摄像头模组 M3", "stage": "concept",
         "on_schedule": True, "milestone_pct": 10, "risk": "low",
         "owner": "赵工", "eta": "2027-Q2"},
    ]

    async def get_npi_projects(self) -> list[dict]:
        return self.PROJECTS[:]

    async def get_milestones(self, project_id: str) -> list[dict]:
        """按项目返回里程碑明细（确定性）。"""
        milestones_map = {
            "NPI-001": [
                {"name": "设计冻结", "expected": "2025-12", "actual": "2025-12", "status": "done"},
                {"name": "原型验证", "expected": "2026-02", "actual": "2026-03", "status": "done"},
                {"name": "小批量试产", "expected": "2026-04", "actual": "2026-05", "status": "done"},
                {"name": "客户认证", "expected": "2026-06", "actual": None, "status": "in_progress"},
                {"name": "量产放行", "expected": "2026-08", "actual": None, "status": "pending"},
            ],
            "NPI-002": [
                {"name": "设计冻结", "expected": "2026-03", "actual": "2026-03", "status": "done"},
                {"name": "原型验证", "expected": "2026-05", "actual": None, "status": "in_progress"},
                {"name": "小批量试产", "expected": "2026-08", "actual": None, "status": "pending"},
            ],
            "NPI-003": [
                {"name": "需求评审", "expected": "2026-04", "actual": "2026-04", "status": "done"},
                {"name": "原理图设计", "expected": "2026-06", "actual": "2026-06", "status": "done"},
                {"name": "关键器件选型", "expected": "2026-06", "actual": None, "status": "delayed"},
                {"name": "PCB Layout", "expected": "2026-08", "actual": None, "status": "pending"},
            ],
        }
        return milestones_map.get(project_id, [])

    async def expedite_project(self, project_id: str, action: str) -> dict:
        """授权内行动：对延后或有风险项目生成加速推进建议。"""
        return {
            "task_id": f"NPI-ACC-{project_id}",
            "project_id": project_id,
            "action": action,
            "note": "已生成 NPI 推进行动项（授权内自动）",
        }
