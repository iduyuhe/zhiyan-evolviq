"""MVP种子数据初始化脚本

生成模拟供应链数据用于离线验证Agent。
"""

import json
import random
from pathlib import Path


def generate_materials(n: int = 30) -> list[dict]:
    """生成物料主数据"""
    categories = ["电阻", "电容", "IC", "连接器", "PCB", "二极管", "三极管", "传感器"]
    suppliers = ["风华高科", "三星电机", "村田", "国巨", "TDK", "兆易创新", "TI", "ON Semiconductor"]

    materials = []
    for i in range(n):
        cat = random.choice(categories)
        materials.append({
            "id": f"MAT-{i+1:04d}",
            "code": f"{cat[:3].upper()}-{i+1:04d}",
            "name": f"{cat} {random.choice(['贴片', '直插', '高频', '功率'])}-{random.randint(100, 999)}",
            "category": cat,
            "unit": "pcs",
            "price": round(random.uniform(0.01, 50.0), 4),
            "supplier": random.choice(suppliers),
            "lead_time_days": random.randint(3, 60),
        })
    return materials


def generate_bom(product_name: str = "NPI-PCBA-007", n_items: int = 10) -> dict:
    """生成BOM清单"""
    materials = generate_materials(n_items)
    items = []
    for i, mat in enumerate(materials):
        items.append({
            "material_code": mat["code"],
            "name": mat["name"],
            "qty": random.randint(500, 5000),
            "ref": f"R{i+1}",
        })
    return {
        "bom_id": f"BOM-{product_name}",
        "product_name": product_name,
        "version": "1.0",
        "total_qty": sum(item["qty"] for item in items),
        "items": items,
        "materials": materials,
    }


def generate_po_for_bom(bom: dict) -> list[dict]:
    """根据BOM生成PO数据"""
    pos = []
    for item in bom["items"]:
        pos.append({
            "po": f"PO-2026-{random.randint(1, 999):04d}",
            "material_code": item["material_code"],
            "qty": item["qty"] * random.randint(1, 3),
            "expected": f"2026-0{random.randint(7, 8)}-{random.randint(10, 30):02d}",
            "status": random.choice(["open", "confirmed", "in_transit", "delayed"]),
        })
    return pos


def generate_inventory_for_bom(bom: dict) -> dict:
    """根据BOM生成库存数据"""
    inv = {}
    for item in bom["items"]:
        inv[item["material_code"]] = {
            "on_hand": random.randint(0, item["qty"] * 2),
            "reserved": random.randint(0, int(item["qty"] * 0.3)),
            "warehouse": random.choice(["A1", "A2", "B1", "B2", "C1"]),
        }
    return inv


def main():
    output_dir = Path("data/seed")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成种子BOM数据
    bom = generate_bom()
    (output_dir / "bom_npi_007.json").write_text(
        json.dumps(bom, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    pos = generate_po_for_bom(bom)
    (output_dir / "po_data.json").write_text(
        json.dumps(pos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    inv = generate_inventory_for_bom(bom)
    (output_dir / "inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"✅ 种子数据已生成：")
    print(f"   BOM: {bom['product_name']} ({len(bom['items'])}项物料)")
    print(f"   PO: {len(pos)} 条订单")
    print(f"   库存: {len(inv)} 项")
    print(f"   路径: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
