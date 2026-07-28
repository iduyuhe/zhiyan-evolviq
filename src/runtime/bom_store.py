"""BOM 存储 + 解析 + 行情×BOM 毛利影响测算（S2-5，#311）

信任爬梯③价值跳变样板：企业只上传 1 份 BOM（不接系统、不进内网），
平台即用第⑥路行情信号自动测算「原材料涨价对该产品物料成本/毛利的影响」。

设计：
- 解析：支持 CSV 文本与 JSON 数组两种格式，表头中英文自适应
  （material/物料/名称, qty/数量/用量, unit_price/单价/价格）。
- 存储：与 tenant_store/env_subscription_store 同构——内存权威 + DB
  best-effort 持久化，db 不可达自动降级（韧性铁律）。
- 测算：从 UNS environment 路取行情信号（source=market），抽取
  MAT: 实体 + 价格变动百分比（正则），与 BOM 物料名双向包含匹配，
  按 qty×unit_price 成本占比折算影响金额。
- 事实锚点纪律：只基于信号中出现的百分比测算，无法解析出百分比的
  信号仅列为「关注项」，绝不臆造数字。
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from src.common import db
from src.runtime.models.bom_upload import BomUpload

logger = logging.getLogger(__name__)

# 表头别名（小写匹配）
_MATERIAL_KEYS = ["material", "物料", "物料名称", "名称", "name", "料号", "part"]
_QTY_KEYS = ["qty", "quantity", "数量", "用量", "usage"]
_PRICE_KEYS = ["unit_price", "price", "单价", "价格", "unit cost", "单位成本"]

# 价格变动抽取：「上行约2.1%」「环比上涨 3%」「回落1.5%」…
_PCT_RE = re.compile(r"([+-]?\d+(?:\.\d+)?)\s*%")
_DOWN_WORDS = ("回落", "下行", "下降", "下跌", "降价", "走低", "回调")


class BomParseError(Exception):
    """BOM 解析失败（格式/字段缺失），API 层转 422。"""


def _pick(row: dict, keys: list[str]) -> str | None:
    low = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
    for k in keys:
        if k in low and str(low[k]).strip():
            return str(low[k]).strip()
    return None


def _to_float(v: str, field: str, line: int) -> float:
    try:
        return float(str(v).replace(",", "").replace("¥", "").replace("￥", ""))
    except Exception:
        raise BomParseError(f"第 {line} 行 {field} 不是数字：{v!r}")


def parse_bom(content: str, filename: str = "") -> list[dict]:
    """解析 BOM 文本（CSV 或 JSON 数组）→ [{material, qty, unit_price, cost}]。"""
    text = (content or "").strip()
    if not text:
        raise BomParseError("文件内容为空")
    rows: list[dict]
    if text.startswith("["):  # JSON 数组
        try:
            data = json.loads(text)
            assert isinstance(data, list)
            rows = [dict(r) for r in data]
        except BomParseError:
            raise
        except Exception:
            raise BomParseError("JSON 格式无效（应为对象数组）")
    else:  # CSV
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = [dict(r) for r in reader]
        except Exception:
            raise BomParseError("CSV 解析失败")
    if not rows:
        raise BomParseError("未解析到任何 BOM 行")

    items: list[dict] = []
    for i, row in enumerate(rows, start=2):
        material = _pick(row, _MATERIAL_KEYS)
        if not material:
            raise BomParseError(
                f"第 {i} 行缺少物料名称列（支持表头：{'/'.join(_MATERIAL_KEYS[:4])}…）"
            )
        qty = _to_float(_pick(row, _QTY_KEYS) or "1", "数量", i)
        price = _to_float(_pick(row, _PRICE_KEYS) or "0", "单价", i)
        items.append({
            "material": material[:120],
            "qty": qty,
            "unit_price": price,
            "cost": round(qty * price, 4),
        })
    if len(items) > 500:
        raise BomParseError(f"BOM 行数 {len(items)} 超上限 500（爬梯③为轻量文件级）")
    return items


def _signal_pct(text: str) -> float | None:
    """从信号文本抽取价格变动百分比（含方向）；抽不出返回 None（不臆造）。"""
    m = _PCT_RE.search(text)
    if not m:
        return None
    pct = float(m.group(1))
    if pct > 0 and any(w in text for w in _DOWN_WORDS):
        pct = -pct
    return pct


def _mat_of(signal: dict) -> list[str]:
    return [
        str(e)[4:].strip()
        for e in (signal.get("entities") or [])
        if str(e).startswith("MAT:") and str(e)[4:].strip()
    ]


def _match(material: str, mat_entity: str) -> bool:
    a, b = material.lower(), mat_entity.lower()
    return a in b or b in a


class BomStore:
    """内存权威 + DB best-effort（与 tenant_store 同构韧性降级）。"""

    def __init__(self) -> None:
        self._mem: dict[str, dict] = {}  # id -> record dict（含 items）

    async def init(self) -> None:
        if not db.db_available or db.async_session is None:
            logger.info("📄 BOM 存储：DB 不可用，内存模式")
            return
        try:
            from sqlalchemy import select

            async with db.async_session() as s:
                rows = (await s.execute(select(BomUpload))).scalars().all()
                for r in rows:
                    self._mem[r.id] = r.to_dict(with_items=True)
            logger.info(f"✅ BOM 记录恢复：{len(self._mem)} 份")
        except Exception as e:
            logger.warning(f"⚠️ BOM 记录恢复失败，降级内存态：{e}")

    # ---------- 查询 ----------
    def list_for(self, tenant_id: str) -> list[dict]:
        out = [dict(r, items=None) for r in self._mem.values() if r["tenant_id"] == tenant_id]
        for r in out:
            r.pop("items", None)
        return sorted(out, key=lambda r: r.get("created_at") or "", reverse=True)

    def get(self, tenant_id: str, bom_id: str) -> dict | None:
        r = self._mem.get(bom_id)
        return r if r and r["tenant_id"] == tenant_id else None

    def has_bom(self, tenant_id: str) -> bool:
        return any(r["tenant_id"] == tenant_id for r in self._mem.values())

    # ---------- 写入 ----------
    async def save(self, tenant_id: str, filename: str, product_name: str,
                   items: list[dict]) -> dict:
        rec_id = str(uuid.uuid4())
        total = round(sum(i["cost"] for i in items), 2)
        record = {
            "id": rec_id,
            "tenant_id": tenant_id,
            "filename": filename[:255],
            "product_name": (product_name or "")[:255],
            "item_count": len(items),
            "total_material_cost": total,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }
        self._mem[rec_id] = record
        if db.db_available and db.async_session is not None:
            try:
                async with db.async_session() as s:
                    s.add(BomUpload(
                        id=rec_id, tenant_id=tenant_id, filename=record["filename"],
                        product_name=record["product_name"], item_count=len(items),
                        total_material_cost=total, items_json=json.dumps(items, ensure_ascii=False),
                    ))
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ BOM 持久化失败（内存态继续）：{e}")
        out = dict(record)
        out.pop("items", None)
        return out

    async def delete(self, tenant_id: str, bom_id: str) -> bool:
        r = self._mem.get(bom_id)
        if not r or r["tenant_id"] != tenant_id:
            return False
        self._mem.pop(bom_id, None)
        if db.db_available and db.async_session is not None:
            try:
                from sqlalchemy import delete as sa_delete

                async with db.async_session() as s:
                    await s.execute(sa_delete(BomUpload).where(BomUpload.id == bom_id))
                    await s.commit()
            except Exception as e:
                logger.warning(f"⚠️ BOM 删除持久化失败：{e}")
        return True

    # ---------- 行情 × BOM 毛利影响测算 ----------
    def margin_impact(self, tenant_id: str, bom_id: str, signals: list[dict]) -> dict:
        """价值跳变核心：行情信号 × BOM 物料 → 成本/毛利影响。"""
        rec = self.get(tenant_id, bom_id)
        if rec is None:
            raise KeyError(bom_id)
        items = rec.get("items") or []
        total = rec["total_material_cost"] or 0.0

        impacts: list[dict] = []
        watchlist: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for sig in signals:
            payload = sig.get("payload") or {}
            text = f"{payload.get('title', '')} {payload.get('content', '')}"
            mats = _mat_of(sig) or _mat_of(payload)
            if not mats:
                continue
            pct = _signal_pct(text)
            for mat in mats:
                for it in items:
                    if not _match(it["material"], mat):
                        continue
                    key = (it["material"], mat)
                    if key in seen:
                        continue
                    seen.add(key)
                    entry = {
                        "material": it["material"],
                        "matched_entity": mat,
                        "signal_title": str(payload.get("title", ""))[:120],
                        "item_cost": it["cost"],
                        "cost_share_pct": round(it["cost"] / total * 100, 2) if total else 0.0,
                    }
                    if pct is None:
                        watchlist.append(entry)  # 无量化数字→只关注，不臆造
                    else:
                        delta = round(it["cost"] * pct / 100.0, 2)
                        impacts.append({**entry, "price_change_pct": pct,
                                        "cost_delta": delta})
        delta_total = round(sum(i["cost_delta"] for i in impacts), 2)
        return {
            "bom_id": bom_id,
            "product_name": rec["product_name"] or rec["filename"],
            "item_count": rec["item_count"],
            "total_material_cost": total,
            "impacts": impacts,
            "watchlist": watchlist,
            "cost_delta_total": delta_total,
            "cost_delta_pct": round(delta_total / total * 100, 2) if total else 0.0,
            "signals_scanned": len(signals),
            "summary": (
                f"扫描 {len(signals)} 条行情信号，命中 {len(impacts)} 项量化影响："
                f"物料成本变动 {delta_total:+.2f} 元（{(delta_total / total * 100) if total else 0:+.2f}%）"
                if impacts else
                f"扫描 {len(signals)} 条行情信号，暂无可量化的物料价格影响"
                + (f"；{len(watchlist)} 项进入关注清单" if watchlist else "")
            ),
        }


bom_store = BomStore()
