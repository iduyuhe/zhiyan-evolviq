"""效果报告API——量化Agent自治价值

聚合平台级指标：自主执行率、节省工时、异常准确率、介入处理率。
对应策划方案 模块四「效果报告」(MVP必修)。

指标基线：
- 自主执行率目标 > 70%
- 每次自主动作等效节省 ~12 分钟人工
- 异常准确率 = 人类批准数 / 介入决策总数
"""

from fastapi import APIRouter

from src.runtime.core.metrics import metrics
from src.runtime.core.intervention import intervention_queue
from src.runtime.core.authorization import authorization

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/effect")
async def effect_report():
    """效果报告——Agent自治价值量化"""
    report = metrics.effect_report()
    report["interventions"] = intervention_queue.stats()
    report["boundaries_active"] = sum(1 for b in authorization.list() if b.enabled)
    return report
