"""S2-5 #311：BOM 上传 + 行情×BOM 毛利影响测算 专项测试

覆盖：解析器（CSV/JSON/中文表头/坏数据）、毛利测算（方向/金额/关注清单/
不臆造）、信任爬梯③单一语义源（BOM=中圈解锁+免限额）、API 闸门与租户隔离。
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from src.runtime.bom_store import (
    BomParseError, BomStore, bom_store, parse_bom, _signal_pct,
)

TENANT_A = "bom-t-a"
TENANT_B = "bom-t-b"

CSV_EN = "material,qty,unit_price\n电解铜,2.5,68.0\n铝锭,1.2,19.5\nCAP-001,120,0.05\n"
CSV_ZH = "物料,数量,单价\n电解铜,2,70\nPCB基板,1,42\n"
JSON_BOM = '[{"material": "电解铜", "qty": 1, "unit_price": 100}]'


def _sig(title: str, content: str, mats: list[str]) -> dict:
    return {
        "payload": {"title": title, "content": content},
        "entities": [f"MAT:{m}" for m in mats],
    }


# ---------- 解析器 ----------

class TestParseBom:
    def test_csv_english_headers(self):
        items = parse_bom(CSV_EN)
        assert len(items) == 3
        assert items[0] == {"material": "电解铜", "qty": 2.5, "unit_price": 68.0, "cost": 170.0}

    def test_csv_chinese_headers(self):
        items = parse_bom(CSV_ZH)
        assert len(items) == 2
        assert items[1]["cost"] == 42.0

    def test_json_array(self):
        items = parse_bom(JSON_BOM)
        assert items[0]["cost"] == 100.0

    def test_empty_content_rejected(self):
        with pytest.raises(BomParseError):
            parse_bom("   ")

    def test_missing_material_column(self):
        with pytest.raises(BomParseError, match="物料名称"):
            parse_bom("qty,unit_price\n1,2\n")

    def test_bad_number(self):
        with pytest.raises(BomParseError, match="不是数字"):
            parse_bom("material,qty,unit_price\n铜,abc,1\n")

    def test_row_limit(self):
        rows = "material,qty,unit_price\n" + "\n".join(f"M{i},1,1" for i in range(501))
        with pytest.raises(BomParseError, match="上限"):
            parse_bom(rows)


# ---------- 百分比抽取（事实锚点：抽不出=None） ----------

class TestSignalPct:
    def test_up(self):
        assert _signal_pct("均价环比上行约2.1%") == 2.1

    def test_down_words_flip_sign(self):
        assert _signal_pct("价格回落1.5%") == -1.5

    def test_explicit_negative(self):
        assert _signal_pct("变动 -3%") == -3.0

    def test_no_number_returns_none(self):
        assert _signal_pct("交期稳定、价格平稳") is None


# ---------- 毛利影响测算 ----------

class TestMarginImpact:
    @pytest.mark.asyncio
    async def test_impact_math_and_watchlist(self):
        store = BomStore()
        rec = await store.save(TENANT_A, "b.csv", "产品X", parse_bom(CSV_EN))
        signals = [
            _sig("铜价周报", "电解铜均价环比上行约2.0%", ["电解铜"]),
            _sig("MLCC 简报", "主流料号价格平稳", ["CAP-001"]),  # 无数字→关注清单
            _sig("钢材快报", "螺纹钢上行5%", ["螺纹钢"]),  # 不在 BOM→忽略
        ]
        out = store.margin_impact(TENANT_A, rec["id"], signals)
        assert len(out["impacts"]) == 1
        imp = out["impacts"][0]
        # 电解铜 cost=170.0，+2% → +3.4
        assert imp["cost_delta"] == 3.4
        assert imp["price_change_pct"] == 2.0
        assert out["cost_delta_total"] == 3.4
        assert len(out["watchlist"]) == 1
        assert out["watchlist"][0]["material"] == "CAP-001"

    @pytest.mark.asyncio
    async def test_tenant_isolation(self):
        store = BomStore()
        rec = await store.save(TENANT_A, "a.csv", "", parse_bom(JSON_BOM))
        assert store.get(TENANT_B, rec["id"]) is None
        with pytest.raises(KeyError):
            store.margin_impact(TENANT_B, rec["id"], [])
        assert store.list_for(TENANT_B) == []
        assert store.has_bom(TENANT_A) and not store.has_bom(TENANT_B)

    @pytest.mark.asyncio
    async def test_no_signals_no_fabrication(self):
        store = BomStore()
        rec = await store.save(TENANT_A, "a.csv", "", parse_bom(JSON_BOM))
        out = store.margin_impact(TENANT_A, rec["id"], [])
        assert out["impacts"] == [] and out["cost_delta_total"] == 0.0


# ---------- 信任爬梯③单一语义源 ----------

class TestTrustLadder:
    @pytest.mark.asyncio
    async def test_bom_unlocks_middle_and_unlimits(self, monkeypatch):
        from src.runtime import usage_meter as um
        from src.runtime.unlock_map import current_circle, trust_ladder_reached

        monkeypatch.setattr(um, "ENFORCE", True)
        tid = "bom-ladder-t"
        assert not trust_ladder_reached(tid)
        assert current_circle(tid) == "outer"
        assert um.usage_meter.is_unlimited(tid) is False

        rec = await bom_store.save(tid, "l.csv", "", parse_bom(JSON_BOM))
        try:
            assert trust_ladder_reached(tid)
            assert current_circle(tid) == "middle"
            assert um.usage_meter.is_unlimited(tid) is True
        finally:
            await bom_store.delete(tid, rec["id"])
        assert current_circle(tid) == "outer"


# ---------- API ----------

def _client():
    from src.runtime.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


class TestBomAPI:
    @pytest.mark.asyncio
    async def test_preview_gate_then_upload(self):
        async with _client() as c:
            # 闸门：坏文件 422
            r = await c.post("/bom/preview", json={"filename": "x.csv", "content": "qty\n1"},
                             headers={"X-Tenant-Key": "bom-api-t"})
            assert r.status_code == 422
            # 好文件预览通过（不落盘）
            r = await c.post("/bom/preview", json={"filename": "x.csv", "content": CSV_EN},
                             headers={"X-Tenant-Key": "bom-api-t"})
            assert r.status_code == 200
            assert r.json()["item_count"] == 3
            r0 = await c.get("/bom", headers={"X-Tenant-Key": "bom-api-t"})
            assert r0.json()["boms"] == []
            # 上传：落盘 + 内嵌首测算 + 圈层跳变
            r = await c.post("/bom/upload",
                             json={"filename": "x.csv", "content": CSV_EN, "product_name": "P1"},
                             headers={"X-Tenant-Key": "bom-api-t"})
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "uploaded"
            assert data["current_circle"] == "middle"  # 价值跳变
            assert data["margin_impact"] is not None
            bom_id = data["bom"]["id"]
            # margin-impact 可反复调用
            r = await c.get(f"/bom/{bom_id}/margin-impact",
                            headers={"X-Tenant-Key": "bom-api-t"})
            assert r.status_code == 200
            assert "summary" in r.json()
            # 租户隔离：B 看不到 A 的 BOM
            r = await c.get(f"/bom/{bom_id}", headers={"X-Tenant-Key": "bom-api-other"})
            assert r.status_code == 404
            # 清理
            r = await c.delete(f"/bom/{bom_id}", headers={"X-Tenant-Key": "bom-api-t"})
            assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_bad_file_422(self):
        async with _client() as c:
            r = await c.post("/bom/upload", json={"filename": "x.csv", "content": ""},
                             headers={"X-Tenant-Key": "bom-api-t2"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_unlock_progress_reflects_bom(self):
        """#310 解锁视图与 BOM 语义同源：上传后 unlock-progress 显示 middle。"""
        async with _client() as c:
            r = await c.post("/bom/upload", json={"filename": "u.csv", "content": CSV_ZH},
                             headers={"X-Tenant-Key": "bom-unlock-t"})
            bom_id = r.json()["bom"]["id"]
            try:
                r = await c.get("/environment/unlock-progress",
                                headers={"X-Tenant-Key": "bom-unlock-t"})
                assert r.status_code == 200
                data = r.json()
                assert data["current_circle"] == "middle"
                # 圈层与额度豁免同源：中圈租户必然免限额
                assert data["quota"]["unlimited"] is True
            finally:
                await c.delete(f"/bom/{bom_id}", headers={"X-Tenant-Key": "bom-unlock-t"})
