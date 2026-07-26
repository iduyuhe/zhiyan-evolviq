"""回写审计记录字段映射——不同 ERP/MES 的 schema 适配层（v28.3）

问题：各家 ERP/MES 审计接口字段名不同（如 SAP 习惯 DecisionNo/CreatedBy，
用友习惯 djbh/czr）。智衍标准审计记录字段固定为：
    decision_id / agent / decision_type / tenant_id / concluded_at / payload

方案：每个（租户, 系统）可注入一份字段映射表 {标准字段: 目标字段}，
回写 POST 前做**顶层键改名**；未映射字段保持原名（恒等映射为默认）。
同时允许覆写审计端点路径（默认 audit/records）。

注入通道（与数据源配置同一套约定）：
    env（默认租户）：  ZHIYAN_DS_MES_WB_MAP='{"decision_id":"DecisionNo"}'
                      ZHIYAN_DS_MES_WB_PATH='api/v2/audit-trail'
    env（租户 T）：    ZHIYAN_DS_<T>_MES_WB_MAP / ..._WB_PATH
    API 注入：        register_from_config 的 config 里带 wb_field_map / wb_audit_path

韧性铁律：映射 JSON 非法 → 记警告、按恒等映射处理，绝不抛异常。
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# 智衍标准审计记录字段（文档锚点，映射表的合法键集合——超出集合的键忽略并警告）
STANDARD_AUDIT_FIELDS = (
    "decision_id",
    "agent",
    "decision_type",
    "tenant_id",
    "concluded_at",
    "payload",
)

DEFAULT_AUDIT_PATH = "audit/records"


def parse_field_map(raw: str | dict | None, source: str = "") -> dict[str, str]:
    """解析字段映射配置（JSON 字符串或 dict）→ {标准字段: 目标字段}。

    韧性：非法输入返回 {}（恒等映射），只记警告不抛异常。
    """
    if not raw:
        return {}
    data: Any = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"⚠️ 回写字段映射 JSON 非法（{source}），按恒等映射处理：{e}")
            return {}
    if not isinstance(data, dict):
        logger.warning(f"⚠️ 回写字段映射不是对象（{source}），按恒等映射处理")
        return {}
    mapping: dict[str, str] = {}
    for k, v in data.items():
        if k not in STANDARD_AUDIT_FIELDS:
            logger.warning(f"⚠️ 回写字段映射含未知标准字段 {k!r}（{source}），已忽略")
            continue
        if not isinstance(v, str) or not v.strip():
            logger.warning(f"⚠️ 回写字段映射 {k!r} 的目标字段非法（{source}），已忽略")
            continue
        mapping[k] = v.strip()
    return mapping


def apply_field_map(record: dict, mapping: dict[str, str] | None) -> dict:
    """按映射表对审计记录做顶层键改名；未映射键保持原名。

    恒等映射（mapping 为空/None）直接原样返回副本。
    """
    if not mapping:
        return dict(record)
    out: dict = {}
    for k, v in record.items():
        out[mapping.get(k, k)] = v
    return out
