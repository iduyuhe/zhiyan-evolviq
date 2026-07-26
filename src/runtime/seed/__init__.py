"""行业知识库模板加载器——按 ZHIYAN_INDUSTRY 注入对应种子

每个行业在 data/seed/<industry>/seed.json 提供：
  - kg_facts   : 领域事实候选（注入 kg_facts 提议池，待审批/蓝弧闭环）
  - ontology   : 实体类型 / 关系类型扩展（注入本体扩展提议门）
  - tacit      : 隐性经验（经 UNS human 通道触发真实隐性捕获管线，抽取即锚定）
  - demo       : 该行业的 BOM/库存/PO/设备示例（供 Demo 数据生成器复用）

设计（呼应三主义活循环 + 韧性降级）：
  - 所有注入均为「提议」而非直接落库，由人工审批门 / 蓝弧闭环把关，符合事实锚点铁律。
  - 任一环节失败静默降级并记日志，绝不阻断启动或执行管道。
  - 无 seed 的行业（如默认半导体）直接跳过，行为不变。
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("zhiyan.seed")

# 项目根：src/runtime/seed/__init__.py -> parents[3] = zhiyan/
_ROOT = Path(__file__).resolve().parents[3]
_SEED_ROOT = _ROOT / "data" / "seed"

# 动态发现已配置的行业（含 seed.json 的子目录）
INDUSTRY_SEEDS: dict[str, Path] = {}
if _SEED_ROOT.exists():
    for d in sorted(_SEED_ROOT.iterdir()):
        seed_file = d / "seed.json"
        if d.is_dir() and seed_file.exists():
            INDUSTRY_SEEDS[d.name] = seed_file


def list_industries() -> list[str]:
    """列出所有可用行业模板。"""
    return sorted(INDUSTRY_SEEDS.keys())


def load_industry_seed(industry: str) -> dict[str, Any] | None:
    """读取某行业的种子 JSON；不存在返回 None。"""
    sf = INDUSTRY_SEEDS.get(industry)
    if not sf:
        return None
    try:
        return json.loads(sf.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"⚠️ 行业种子读取失败 {industry}: {e}")
        return None


def bootstrap_industry(industry: str, tenant_id: str = "default") -> dict:
    """把行业种子注入平台三大回路（KG事实 / 本体扩展 / 隐性捕获）。

    返回注入统计；行业不存在或为空时 status=skipped。
    """
    seed = load_industry_seed(industry)
    if not seed:
        logger.info(f"🧩 无行业种子 [{industry}]，跳过注入（默认半导体/空数据）")
        return {"status": "skipped", "industry": industry}

    stats = {"kg_facts": 0, "ontology_entities": 0, "ontology_relations": 0, "tacit": 0}
    label = seed.get("label", industry)

    # 1) KG 事实 → kg_facts 提议池
    try:
        from src.runtime.evolution import kg_facts as kf

        for f in seed.get("kg_facts", []):
            try:
                kf.propose(
                    tenant_id=tenant_id,
                    agent=f.get("agent", "industry_seed"),
                    subject=f["subject"],
                    predicate=f["predicate"],
                    object_val=f["object"],
                    source=f.get("source", "industry-seed"),
                    confidence=float(f.get("confidence", 0.8)),
                    note=f.get("note", ""),
                )
                stats["kg_facts"] += 1
            except Exception as e:
                logger.warning(f"  KG 事实注入跳过：{f} -> {e}")
    except Exception as e:
        logger.warning(f"⚠️ kg_facts 不可用，跳过事实注入：{e}")

    # 2) 本体扩展 → 本体扩展提议门
    try:
        from src.runtime.evolution.ontology import ontology

        for e in seed.get("ontology", {}).get("entities", []):
            try:
                ontology.propose_extension("entity_type", e["name"], e.get("desc", ""))
                stats["ontology_entities"] += 1
            except Exception:
                pass  # 已存在则忽略
        for r in seed.get("ontology", {}).get("relations", []):
            try:
                ontology.propose_extension("relationship_type", r["name"], r.get("desc", ""))
                stats["ontology_relations"] += 1
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"⚠️ 本体存储不可用，跳过本体扩展：{e}")

    # 3) 隐性经验 → UNS human 通道（触发真实隐性捕获管线，抽取即锚定）
    try:
        from src.runtime.uns import uns

        for t in seed.get("tacit", []):
            try:
                uns.publish_human(
                    source=t.get("source", "industry-seed"),
                    payload={"note": t["text"], "category": t.get("category", "")},
                    type="tacit_judgment",
                )
                stats["tacit"] += 1
            except Exception as e:
                logger.warning(f"  隐性经验注入跳过：{t} -> {e}")
    except Exception as e:
        logger.warning(f"⚠️ UNS 不可用，跳过隐性经验注入：{e}")

    logger.info(
        f"🧩 行业种子已注入 [{label}]：KG事实 {stats['kg_facts']} / "
        f"本体 {stats['ontology_entities']}+{stats['ontology_relations']} / 隐性 {stats['tacit']}"
    )
    return {"status": "ok", "industry": industry, "label": label, **stats}
