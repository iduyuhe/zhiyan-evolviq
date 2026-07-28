"""平台建议模型（S2 v30.5 β · G5 轨道二 platform_insight）

与真实外部情报（environment 路，credibility=official）严格区分：
- 这是「智衍平台」基于真实情报生成的建议/解读，透明标注 credibility="platform"，
  在 feed 中 kind="platform_insight"，前端明示「来自智衍平台的建议」，绝不伪装成官方情报（F4 红线）。
- 由 platform_insight_store 规则化派生并持久化；tenant_id 固定 "default"（平台级共享池，
  不含任何租户私有信息），对所有租户可见——与「抓取共享、语义隔离」两层制一致。

持久化：db 可用落库，重启恢复；db 不可用降级内存态。
"""

import json
import time
import uuid

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.runtime.models.base import Base


class PlatformInsight(Base):
    """平台建议（G5 轨道二）——智衍平台基于真实情报生成、透明标注的建议/解读。"""

    __tablename__ = "platform_insights"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: uuid.uuid4().hex[:16])
    # 共享池：平台建议不含租户私有信息，对所有租户可见（F4 透明，不泄露租户数据）
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, default="default")
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    # 去重键：基于哪条真实信号 + 哪套模板（sig_id|template_key），防重复生成
    sig_ref: Mapped[str] = mapped_column(String(200), index=True)
    # 透明溯源：引用的真实情报来源 [{signal_id, source, title}]
    based_on: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 固定 platform：明确不是 official/authoritative/general（F4 红线）
    credibility: Mapped[str] = mapped_column(String(16), default="platform")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    ts: Mapped[float] = mapped_column(Float, default=time.time)

    def to_dict(self, include_internal: bool = False) -> dict:
        d = {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "content": self.content,
            "based_on": json.loads(self.based_on) if self.based_on else [],
            "credibility": self.credibility,
            "confidence": self.confidence,
            "ts": self.ts,
            "kind": "platform_insight",
        }
        if include_internal:
            d["sig_ref"] = self.sig_ref
        return d
