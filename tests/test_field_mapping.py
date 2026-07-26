"""回写字段映射测试（v28.3：不同 ERP/MES 审计 schema 适配）"""

import json

import pytest

from src.runtime.data_sources.field_mapping import (
    DEFAULT_AUDIT_PATH,
    apply_field_map,
    parse_field_map,
)
from src.runtime.data_sources.connectors.domain import MESConnector, ERPConnector
from src.runtime.data_sources.config import build_connector


# ---------------- parse_field_map ----------------

def test_parse_from_json_string():
    m = parse_field_map('{"decision_id": "DecisionNo", "agent": "CreatedBy"}')
    assert m == {"decision_id": "DecisionNo", "agent": "CreatedBy"}


def test_parse_from_dict():
    m = parse_field_map({"payload": "Body"})
    assert m == {"payload": "Body"}


def test_parse_invalid_json_falls_back_identity():
    assert parse_field_map("{not json") == {}


def test_parse_non_dict_falls_back_identity():
    assert parse_field_map('["a"]') == {}
    assert parse_field_map(None) == {}
    assert parse_field_map("") == {}


def test_parse_ignores_unknown_and_bad_targets():
    m = parse_field_map({"decision_id": "OK", "not_a_field": "X", "agent": "", "tenant_id": 3})
    assert m == {"decision_id": "OK"}


# ---------------- apply_field_map ----------------

def test_apply_identity_when_empty():
    rec = {"decision_id": "d1", "agent": "a"}
    out = apply_field_map(rec, {})
    assert out == rec
    assert out is not rec  # 副本，不改原 dict


def test_apply_renames_mapped_keeps_rest():
    rec = {"decision_id": "d1", "agent": "a", "payload": {"k": 1}}
    out = apply_field_map(rec, {"decision_id": "DecisionNo"})
    assert out == {"DecisionNo": "d1", "agent": "a", "payload": {"k": 1}}


# ---------------- 连接器集成（POST 前改名 + 路径覆写） ----------------

class _CaptureMES(MESConnector):
    """捕获 _post 的路径与请求体，不真发 HTTP。"""

    def __init__(self, **kwargs):
        super().__init__(base_url="http://fake-mes.local", **kwargs)
        self.captured: tuple[str, dict] | None = None

    async def _post(self, path: str, json_body: dict):
        self.captured = (path, json_body)
        return {"ok": True}


@pytest.mark.asyncio
async def test_connector_applies_mapping_and_custom_path():
    c = _CaptureMES(
        wb_field_map='{"decision_id": "djbh", "agent": "czr"}',
        wb_audit_path="/api/v2/audit-trail",
    )
    rec = {"decision_id": "D-9", "agent": "supply_chain", "payload": {"x": 1}}
    resp = await c.post_audit_record(rec)
    assert resp == {"ok": True}
    path, body = c.captured
    assert path == "api/v2/audit-trail"  # lstrip('/')
    assert body == {"djbh": "D-9", "czr": "supply_chain", "payload": {"x": 1}}


@pytest.mark.asyncio
async def test_connector_default_identity_and_path():
    c = _CaptureMES()
    rec = {"decision_id": "D-1", "agent": "a"}
    await c.post_audit_record(rec)
    path, body = c.captured
    assert path == DEFAULT_AUDIT_PATH
    assert body == rec


# ---------------- 配置通道（API 注入 build_connector） ----------------

def test_build_connector_injects_wb_config():
    c = build_connector(
        "erp",
        {
            "base_url": "http://erp.local",
            "wb_field_map": {"decision_type": "BizType"},
            "wb_audit_path": "audit/v1",
        },
        tenant_id="t1",
    )
    assert isinstance(c, ERPConnector)
    assert c.wb_field_map == {"decision_type": "BizType"}
    assert c.wb_audit_path == "audit/v1"


def test_build_connector_defaults():
    c = build_connector("mes", {"base_url": "http://mes.local"})
    assert isinstance(c, MESConnector)
    assert c.wb_field_map == {}
    assert c.wb_audit_path == DEFAULT_AUDIT_PATH


# ---------------- env 通道 ----------------

def test_env_channel(monkeypatch):
    from src.runtime.data_sources.config import load_sources_for_tenant
    from src.runtime.data_sources.registry import registry
    from src.runtime.data_sources.base import DataSourceKind

    monkeypatch.setenv("ZHIYAN_DS_MES_URL", "http://env-mes.local")
    monkeypatch.setenv("ZHIYAN_DS_MES_WB_MAP", json.dumps({"agent": "Operator"}))
    monkeypatch.setenv("ZHIYAN_DS_MES_WB_PATH", "custom/audit")
    load_sources_for_tenant("default")
    c = registry.get(DataSourceKind.MES, tenant_id="default")
    assert c is not None
    assert c.wb_field_map == {"agent": "Operator"}
    assert c.wb_audit_path == "custom/audit"
    # 清理：重新按无 env 装载，避免污染其他用例
    monkeypatch.delenv("ZHIYAN_DS_MES_URL")
    monkeypatch.delenv("ZHIYAN_DS_MES_WB_MAP")
    monkeypatch.delenv("ZHIYAN_DS_MES_WB_PATH")
    registry.unregister(DataSourceKind.MES, tenant_id="default")
