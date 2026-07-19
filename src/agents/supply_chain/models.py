"""供应链Agent专用数据模型"""

from pydantic import BaseModel


class SupplyGoal(BaseModel):
    """用户设定的供应链管理目标"""
    raw_text: str
    bom_id: str | None = None
    check_frequency: str = "每2小时"
    risk_threshold: float = 0.3  # 缺料风险>30%触发预警
    auto_alternative: bool = True  # 是否自动检索替代方案
    max_price_variation: float = 0.05  # 5%价格波动容忍度
    auto_lock: bool = True  # 授权内可自动锁定库存


class Step(BaseModel):
    """规划中的一步"""
    order: int
    action: str
    tool: str
    params: dict = {}
    estimated_duration: str = ""


class AgentPlan(BaseModel):
    """Agent生成的执行规划"""
    understanding: str
    required_data: list[str]
    steps: list[Step]
    autonomous_actions: list[str]
    approval_required: list[str]


class ExecutionResult(BaseModel):
    """执行结果"""
    session_id: str
    status: str
    summary: str
    actions_taken: list[dict] = []
    warnings: list[str] = []
    completeness_pct: float = 0.0
    detail: dict = {}
