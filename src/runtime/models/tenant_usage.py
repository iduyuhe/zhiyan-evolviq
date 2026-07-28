"""租户用量计数模型（S2 v30.5 β —— 免费额度计量，#309 S2-1b）

免费额度三维（总纲 §3 S2-3，发布前杜总可调）：
1. 信息源数 ≤ 3      —— 已在 env_subscription_store.upsert() 落地（#307）。
2. 每日信号 ≤ 50 条   —— 本表 metric=daily_signals，period=YYYY-MM-DD。
3. agent 解读 ≤ 30 次/月 —— 本表 metric=monthly_insights，period=YYYY-MM。

设计：
- 一行 = 租户 × 指标 × 计费周期（主键拼接，天然幂等 upsert）。
- 只存计数，不存明细（明细去重集在 usage_meter 内存态，重启丢失可接受——
  丢失方向是「多计不少计」，对平台保守安全）。
- 付费判定不在本表：信任爬梯③（已接第 1 个内部数据源 = gateway_config 非空）
  即免限额，判定在 usage_meter.is_unlimited()。
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base, TimestampMixin


def usage_pk(tenant_id: str, metric: str, period_key: str) -> str:
    """主键：租户 × 指标 × 周期（长度受控：hex16 + 短枚举 + 10 位日期）"""
    return f"{tenant_id}:{metric}:{period_key}"[:120]


class TenantUsage(Base, TimestampMixin):
    """租户用量计数（一租户一指标一周期一行）"""

    __tablename__ = "tenant_usage"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    metric: Mapped[str] = mapped_column(String(32))       # daily_signals | monthly_insights
    period_key: Mapped[str] = mapped_column(String(16))   # YYYY-MM-DD | YYYY-MM
    used: Mapped[int] = mapped_column(Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "metric": self.metric,
            "period_key": self.period_key,
            "used": self.used,
        }
