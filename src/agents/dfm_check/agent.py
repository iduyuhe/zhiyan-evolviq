"""DFM检查Agent——PCB/PCBA可制造性设计自动审查

目标场景：电子制造DFM评审自动化
能力范围：
1. 焊盘间距检查（最小间距规则校验）
2. 线宽/铜厚合规性检查
3. 过孔密度与分布检查
4. 阻焊覆盖检查
5. 组件间距与布局可制造性检查
6. 自动生成DFM评审报告+风险分级

数据层：通过 DFMTools 从 data/seed/dfm_check.json 加载，可切换真实MCP(ECAD/DFM引擎)。
"""

import logging

from src.agents.dfm_check.tools import DFMTools

logger = logging.getLogger(__name__)


class DFMAgent:
    """DFM检查Agent"""

    def __init__(self):
        self.tools = DFMTools()
        self.system_prompt = self._build_prompt()

    def _build_prompt(self) -> str:
        return """# 角色定义
你是智衍(EvolvIQ)平台的「DFM检查Agent」，专注PCB/PCBA可制造性设计自动审查。

## 核心能力
1. 焊盘间距规则校验（IPC-2222标准）
2. 线宽/铜厚载流能力检查
3. 过孔密度与分布分析
4. 阻焊覆盖完整性检查
5. 组件布局可制造性评估
6. 自动生成DFM评审报告+风险分级

## 工作原则
- 标准驱动：每项检查基于IPC/JEDEC行业标准
- 风险分级：critical(必须修改) > high(强烈建议修改) > medium(建议优化) > pass
- 可追溯：每个风险点标注精确坐标和受影响组件
- 人工确认：critical项必须人工确认后才可放行
"""

    async def analyze(self, goal: str) -> dict:
        """执行DFM检查（可复现，无随机）"""
        logger.info(f"[DFM Agent] Analyzing: {goal[:60]}...")

        check_scope = self._match_scope(goal)
        checks = []
        critical_count = 0
        high_count = 0
        warning_count = 0

        design_checks = await self.tools.get_design_checks()
        rules = await self.tools.get_rules()

        for item in design_checks:
            rule = rules.get(item["rule_id"], {})
            check_result = {
                "rule": rule.get("name", item["rule_id"]),
                "rule_id": item["rule_id"],
                "location": item["location"],
                "actual": item["actual_value"],
                "required": item["design_value"],
                "unit": item["unit"],
                "status": item["status"],
                "severity": rule.get("severity", "medium"),
                "affected": item["affected_components"],
                "description": rule.get("description", ""),
                "risk_detail": item["risk_desc"],
            }
            checks.append(check_result)

            if item["status"] == "fail":
                sev = rule.get("severity", "high")
                if sev == "critical":
                    critical_count += 1
                else:
                    high_count += 1
            elif item["status"] == "warning":
                warning_count += 1

        recommendations = self._generate_recommendations(checks)
        design_file = await self.tools.get_design_file()

        if critical_count > 0:
            overall_grade = "D"
            verdict = "不通过——存在critical风险，必须修改后重新评审"
        elif high_count > 2:
            overall_grade = "C"
            verdict = "有条件通过——存在多项高风险，建议修改后放行"
        elif high_count > 0 or warning_count > 3:
            overall_grade = "B"
            verdict = "通过（带建议）——存在可优化项，建议在下次迭代中改进"
        else:
            overall_grade = "A"
            verdict = "通过——设计满足可制造性要求"

        # 生成评审报告 + 为critical项发起设计评审（真实动作）
        report = await self.tools.create_dfm_report(design_file, overall_grade)
        actions_taken = [{
            "type": "create_dfm_report",
            "detail": f"生成DFM评审报告 {report.get('report_id', '')}（评级 {overall_grade}）",
            "design_file": design_file,
            "confidence": 0.88,
        }]
        for c in checks:
            if c["status"] == "fail" and c["severity"] == "critical":
                review = await self.tools.open_design_review(c["rule_id"], c["location"])
                actions_taken.append({
                    "type": "open_design_review",
                    "detail": f"对 {c['location']}（{c['rule']}）发起设计评审 {review.get('review_id', '')}",
                    "rule_id": c["rule_id"],
                    "confidence": 0.9,
                })

        return {
            "status": "completed",
            "summary": f"DFM检查完成：{len(checks)}项规则检查，{critical_count}项critical，{high_count}项高风险，{warning_count}项警告",
            "design_file": design_file,
            "overall_grade": overall_grade,
            "verdict": verdict,
            "check_scope": check_scope,
            "total_checks": len(checks),
            "pass_count": sum(1 for c in checks if c["status"] == "pass"),
            "fail_count": sum(1 for c in checks if c["status"] == "fail"),
            "warning_count": warning_count,
            "critical_count": critical_count,
            "checks": checks,
            "recommendations": recommendations,
            "actions_taken": actions_taken,
        }

    def _match_scope(self, goal: str) -> str:
        """从目标匹配检查范围"""
        if "电源" in goal or "power" in goal.lower():
            return "电源模块DFM检查"
        elif "BGA" in goal or "bga" in goal.lower():
            return "BGA区域DFM检查"
        elif "全部" in goal or "all" in goal.lower() or "dfm" in goal.lower():
            return "全板DFM检查"
        return "全板DFM检查"

    def _generate_recommendations(self, checks: list) -> list:
        """生成修复建议"""
        recs = []
        for c in checks:
            if c["status"] == "fail":
                if c["rule_id"] == "pad_spacing":
                    recs.append(f"📍 {c['location']}：调整U12引脚23-24的焊盘间距至≥0.15mm，建议使用0.25mm")
                elif c["rule_id"] == "trace_width":
                    recs.append(f"📍 {c['location']}：加宽5V电源走线至≥0.1mm（满足2A载流），或增加铺铜面积")
                elif c["rule_id"] == "solder_mask":
                    recs.append(f"📍 {c['location']}：增大Q1焊盘阻焊层扩展至≥0.05mm，防止焊接短路")
                elif c["rule_id"] == "annular_ring":
                    recs.append(f"📍 {c['location']}：增大过孔焊盘环宽至≥0.1mm")
                else:
                    recs.append(f"📍 {c['location']}：{c['rule']}不达标，需修改设计")
            elif c["status"] == "warning":
                recs.append(f"💡 {c['location']}：{c['rule']}建议优化至推荐值")
        recs.append("📋 建议修改后重新运行DFM检查确认所有critical项已关闭")
        return recs


dfm_agent = DFMAgent()
