"""面向中芯国际(SMIC)的半导体供应链种子数据

生成符合半导体制造场景的物料数据：
- 硅片、光刻胶、特种气体、靶材、CMP抛光液等
"""

import json
import random
from pathlib import Path

# 半导体制造的核心物料
SEMI_MATERIALS = [
    # 硅片类
    {"code": "SI-001", "name": "8英寸抛光硅片", "cat": "硅片", "supplier": "上海硅产业集团", "lead_time": 30, "price": 85.0},
    {"code": "SI-002", "name": "12英寸抛光硅片", "cat": "硅片", "supplier": "中环股份", "lead_time": 45, "price": 220.0},
    {"code": "SI-003", "name": "SOI硅片 8英寸", "cat": "硅片", "supplier": "上海新傲", "lead_time": 60, "price": 350.0},
    # 光刻胶
    {"code": "PR-001", "name": "ArF光刻胶", "cat": "光刻胶", "supplier": "北京科华", "lead_time": 45, "price": 2800.0},
    {"code": "PR-002", "name": "KrF光刻胶", "cat": "光刻胶", "supplier": "徐州博康", "lead_time": 30, "price": 1500.0},
    {"code": "PR-003", "name": "i-line光刻胶", "cat": "光刻胶", "supplier": "彤程新材", "lead_time": 20, "price": 680.0},
    # 特种气体
    {"code": "GAS-001", "name": "高纯氮气 99.9999%", "cat": "特种气体", "supplier": "华特气体", "lead_time": 7, "price": 45.0},
    {"code": "GAS-002", "name": "高纯氩气 99.9999%", "cat": "特种气体", "supplier": "杭氧股份", "lead_time": 7, "price": 120.0},
    {"code": "GAS-003", "name": "三氟化氮 NF3", "cat": "特种气体", "supplier": "中船重工718所", "lead_time": 30, "price": 380.0},
    {"code": "GAS-004", "name": "六氟化钨 WF6", "cat": "特种气体", "supplier": "华特气体", "lead_time": 30, "price": 520.0},
    # 靶材
    {"code": "TGT-001", "name": "钛靶 Ti 99.995%", "cat": "靶材", "supplier": "江丰电子", "lead_time": 45, "price": 4500.0},
    {"code": "TGT-002", "name": "铜靶 Cu 99.99%", "cat": "靶材", "supplier": "有研新材", "lead_time": 45, "price": 3200.0},
    {"code": "TGT-003", "name": "铝靶 Al 99.999%", "cat": "靶材", "supplier": "江丰电子", "lead_time": 30, "price": 1800.0},
    # CMP
    {"code": "CMP-001", "name": "CMP抛光液 OX", "cat": "CMP材料", "supplier": "安集科技", "lead_time": 20, "price": 250.0},
    {"code": "CMP-002", "name": "CMP抛光垫", "cat": "CMP材料", "supplier": "鼎龙股份", "lead_time": 30, "price": 380.0},
    # 设备备件
    {"code": "SPR-001", "name": "石英窗片(光刻机)", "cat": "备件", "supplier": "菲利华", "lead_time": 60, "price": 12500.0},
    {"code": "SPR-002", "name": "O型密封圈 Viton", "cat": "备件", "supplier": "日本バルカー", "lead_time": 90, "price": 85.0},
    {"code": "SPR-003", "name": "聚焦环(刻蚀机)", "cat": "备件", "supplier": "中微公司", "lead_time": 60, "price": 8800.0},
    # 化学品
    {"code": "CHM-001", "name": "显影液 TMAH 2.38%", "cat": "化学品", "supplier": "江化微", "lead_time": 15, "price": 95.0},
    {"code": "CHM-002", "name": "浓硫酸 H2SO4 UP级", "cat": "化学品", "supplier": "晶瑞电材", "lead_time": 10, "price": 55.0},
]


def generate_semi_bom(product_name: str = "SMIC-28nm-Logic") -> dict:
    """生成半导体BOM"""
    items = []
    for mat in SEMI_MATERIALS[:12]:  # 选前12项关键物料
        items.append({
            "material_code": mat["code"],
            "name": mat["name"],
            "qty": random.randint(50, 2000),
            "unit": "片" if "硅片" in mat["cat"] else "瓶" if "气体" in mat["cat"] or "化学品" in mat["cat"] else "个",
        })
    return {
        "bom_id": f"BOM-{product_name}",
        "product_name": product_name,
        "version": "2.0",
        "node": "N85nm/28nm",
        "total_qty": sum(item["qty"] for item in items),
        "items": items,
    }


def generate_semi_inventory(items: list) -> dict:
    """生成半导体库存"""
    inv = {}
    for item in items:
        code = item["material_code"]
        required = item["qty"]
        inv[code] = {
            "on_hand": random.randint(0, int(required * 1.8)),
            "reserved": random.randint(0, int(required * 0.2)),
            "warehouse": random.choice(["FAB1", "FAB2", "WH-Central"]),
            "lot": f"LOT-{random.randint(1000,9999)}",
        }
    return inv


def generate_semi_po(items: list) -> list:
    """生成半导体采购订单"""
    pos = []
    for item in items:
        pos.append({
            "po": f"PO-SMIC-2026-{random.randint(100,999)}",
            "material_code": item["material_code"],
            "qty": item["qty"] * random.randint(1, 3),
            "expected": f"2026-0{random.randint(7,9)}-{random.randint(1,30):02d}",
            "status": random.choice(["in_transit", "confirmed", "delayed", "open"]),
            "supplier": next((m["supplier"] for m in SEMI_MATERIALS if m["code"] == item["material_code"]), "N/A"),
        })
    return pos


def main():
    output_dir = Path("data/seed")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成SMIC场景BOM
    bom = generate_semi_bom()
    (output_dir / "smic_bom.json").write_text(
        json.dumps(bom, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    inv = generate_semi_inventory(bom["items"])
    (output_dir / "smic_inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    pos = generate_semi_po(bom["items"])
    (output_dir / "smic_po.json").write_text(
        json.dumps(pos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"✅ 中芯国际(SMIC)数据已生成：")
    print(f"   BOM: {bom['product_name']} ({bom['node']}) — {len(bom['items'])}项关键物料")
    print(f"   库存: {len(inv)} 项")
    print(f"   PO: {len(pos)} 条订单")
    print(f"   路径: {output_dir.resolve()}")

    # 分类统计
    cats = {}
    for m in SEMI_MATERIALS:
        cats[m['cat']] = cats.get(m['cat'], 0) + 1
    print(f"\n   物料分类:")
    for cat, count in cats.items():
        print(f"     {cat}: {count}项")


if __name__ == "__main__":
    main()
