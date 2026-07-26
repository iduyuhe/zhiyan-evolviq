"""ERP / MES 回写审计桥——智衍决策「落账本」的最小安全通道

战略定位（原生赋能者）：
    智衍不推倒 ERP/MES，而是把 agent 的「决策/审批结论」作为**审计记录**回写业务系统，
    业务系统在自身账本内过账/留痕。智衍因此成为「实时决策脑 + 全息真相源」，
    而不篡夺执行系统的权威账本。

写入语义（审计，非指令下发）：
    POST {system_base_url}/audit/records  {
        decision_id, agent, decision_type, tenant_id,
        concluded_at, payload { ... 决策结论+依据 }
    }

韧性铁律：
    - 连接器未配置/不可达 → 不抛异常，落本地 pending 队列（status=pending），返回 202。
    - POST 失败 → 同样进 pending 队列，供 retry_pending() 周期重试。
    - 全部失败都不阻断 agent 主流程（审计是旁路）。

进程级单例 `writeback_bridge`。
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from src.runtime.data_sources.base import DataSourceKind
from src.runtime.data_sources.registry import registry

logger = logging.getLogger(__name__)


# 系统名 -> 数据源 kind 的映射
_SYSTEM_KIND = {
    "mes": DataSourceKind.MES,
    "erp": DataSourceKind.ERP,
}


@dataclass
class WritebackRecord:
    id: str
    system: str          # mes / erp
    tenant_id: str
    agent: str
    decision_type: str   # 如 supply_risk_approval / energy_conclusion
    payload: dict
    decision_id: str
    status: str = "pending"   # pending | sent | failed
    created_at: float = field(default_factory=time.time)
    sent_at: Optional[float] = None
    error: Optional[str] = None
    response: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "system": self.system,
            "tenant_id": self.tenant_id,
            "agent": self.agent,
            "decision_type": self.decision_type,
            "decision_id": self.decision_id,
            "status": self.status,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
            "error": self.error,
        }


class WritebackBridge:
    """把 agent 决策回写为业务系统审计记录的韧性桥。"""

    def __init__(self):
        self._pending: list[WritebackRecord] = []
        self._sent: list[WritebackRecord] = []
        self._max_kept = 200  # 已发送/失败记录最多保留条数

    # ---------------- 提交 ----------------

    async def submit(
        self,
        system: str,
        agent: str,
        decision_type: str,
        payload: dict,
        tenant_id: str = "default",
        decision_id: Optional[str] = None,
    ) -> dict:
        """提交一条回写。返回 {status, record_id, detail}。"""
        system = (system or "").lower()
        if system not in _SYSTEM_KIND:
            return {"status": "rejected", "detail": f"未知回写系统: {system}（支持 mes/erp）"}
        rec = WritebackRecord(
            id=uuid.uuid4().hex[:12],
            system=system,
            tenant_id=tenant_id,
            agent=agent,
            decision_type=decision_type,
            payload=payload or {},
            decision_id=decision_id or uuid.uuid4().hex[:12],
        )
        connector = registry.get(_SYSTEM_KIND[system], tenant_id=tenant_id)
        if connector is None or not await connector.is_available():
            rec.status = "pending"
            rec.error = "connector_unavailable"
            self._pending.append(rec)
            logger.info(f"📤 回写 {system} 连接器不可用，进 pending 队列（{rec.id}）")
            return {"status": "pending", "record_id": rec.id, "detail": "connector_unavailable"}
        body = {
            "decision_id": rec.decision_id,
            "agent": rec.agent,
            "decision_type": rec.decision_type,
            "tenant_id": rec.tenant_id,
            "concluded_at": rec.created_at,
            "payload": rec.payload,
        }
        try:
            resp = await connector.post_audit_record(body)
            if resp is None:
                # POST 返回 None 视为写回失败（连接器已降级）
                rec.status = "pending"
                rec.error = "post_failed_or_unavailable"
                self._pending.append(rec)
                return {"status": "pending", "record_id": rec.id, "detail": "post_failed"}
            rec.status = "sent"
            rec.sent_at = time.time()
            rec.response = resp if isinstance(resp, dict) else {"raw": str(resp)}
            self._sent.append(rec)
            self._trim()
            logger.info(f"✅ 回写 {system} 审计记录成功（{rec.id}）")
            return {"status": "sent", "record_id": rec.id, "detail": "ok"}
        except Exception as e:  # noqa: BLE001  韧性：任何异常都进 pending
            rec.status = "pending"
            rec.error = str(e)
            self._pending.append(rec)
            logger.warning(f"⚠️ 回写 {system} 异常进 pending：{e}")
            return {"status": "pending", "record_id": rec.id, "detail": f"exception:{e}"}

    # ---------------- 重试 ----------------

    async def retry_pending(self) -> int:
        """重试 pending 队列；返回本次成功发送数。"""
        if not self._pending:
            return 0
        still_pending: list[WritebackRecord] = []
        sent = 0
        for rec in self._pending:
            connector = registry.get(_SYSTEM_KIND[rec.system], tenant_id=rec.tenant_id)
            if connector is None or not await connector.is_available():
                still_pending.append(rec)
                continue
            body = {
                "decision_id": rec.decision_id,
                "agent": rec.agent,
                "decision_type": rec.decision_type,
                "tenant_id": rec.tenant_id,
                "concluded_at": rec.created_at,
                "payload": rec.payload,
            }
            try:
                resp = await connector.post_audit_record(body)
                if resp is None:
                    still_pending.append(rec)
                    continue
                rec.status = "sent"
                rec.sent_at = time.time()
                rec.response = resp if isinstance(resp, dict) else {"raw": str(resp)}
                self._sent.append(rec)
                sent += 1
            except Exception as e:  # noqa: BLE001
                rec.error = str(e)
                still_pending.append(rec)
        self._pending = still_pending
        self._trim()
        if sent:
            logger.info(f"🔁 回写重试成功 {sent} 条，剩余 pending {len(self._pending)}")
        return sent

    # ---------------- 查询 ----------------

    def pending(self) -> list[dict]:
        return [r.to_dict() for r in self._pending]

    def stats(self) -> dict:
        return {
            "pending": len(self._pending),
            "sent_total": len(self._sent),
            "systems": sorted(_SYSTEM_KIND.keys()),
        }

    def _trim(self) -> None:
        if len(self._sent) > self._max_kept:
            self._sent = self._sent[-self._max_kept:]


# 进程级单例
writeback_bridge = WritebackBridge()
