"""行业知识库模板测试——种子加载 / 结构 / 注入统计

不依赖 lifespan（bootstrap_industry 直接调用模块单例，韧性降级）。
"""

import pytest

from src.runtime.seed import bootstrap_industry, list_industries, load_industry_seed

pytestmark = pytest.mark.asyncio


async def test_industries_available():
    inds = list_industries()
    for must in ("shipbuilding", "railway", "electronics"):
        assert must in inds, f"缺少行业模板: {must}"


async def test_load_seed_schema():
    for ind in ("shipbuilding", "railway", "electronics"):
        seed = load_industry_seed(ind)
        assert seed, f"{ind} 种子为空"
        assert seed["industry"] == ind
        for f in seed["kg_facts"]:
            assert {"subject", "predicate", "object"} <= set(f)
        for t in seed["tacit"]:
            assert "text" in t
        assert "entities" in seed["ontology"] and "relations" in seed["ontology"]


async def test_bootstrap_injects():
    s = bootstrap_industry("shipbuilding", tenant_id="default")
    assert s["status"] == "ok"
    assert s["kg_facts"] > 0
    assert s["ontology_entities"] > 0
    assert s["ontology_relations"] > 0
    assert s["tacit"] > 0


async def test_bootstrap_unknown_skips():
    s = bootstrap_industry("__no_such_industry__")
    assert s["status"] == "skipped"
