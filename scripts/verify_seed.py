"""行业知识库模板验证脚本

用法：
  python scripts/verify_seed.py                # 校验全部行业种子 + 试注入
  python scripts/verify_seed.py shipbuilding   # 仅指定行业

校验项：
  1) 每个 seed.json 结构合法（kg_facts/ontology/tacit 字段完整）
  2) 调用 bootstrap_industry 实际注入并返回统计（不阻断，仅打印）
"""

import asyncio
import sys
from pathlib import Path

# 仓库根加入 sys.path（e2e/verify 脚本约定）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.runtime.seed import bootstrap_industry, list_industries, load_industry_seed


def check_schema(industry: str) -> bool:
    seed = load_industry_seed(industry)
    assert seed, f"{industry}: 种子为空"
    assert seed.get("industry") == industry, f"{industry}: industry 字段不匹配"
    assert "kg_facts" in seed and "ontology" in seed and "tacit" in seed, f"{industry}: 缺少核心段"
    for f in seed["kg_facts"]:
        assert {"subject", "predicate", "object"} <= set(f), f"{industry}: kg_fact 缺字段 {f}"
    for t in seed["tacit"]:
        assert "text" in t, f"{industry}: tacit 缺 text {t}"
    print(f"  ✅ {industry}（{seed.get('label','')}）结构合法："
          f"KG {len(seed['kg_facts'])} / 本体 {len(seed['ontology'].get('entities',[]))}+{len(seed['ontology'].get('relations',[]))} / 隐性 {len(seed['tacit'])}")
    return True


async def main():
    targets = sys.argv[1:]
    industries = targets if targets else list_industries()
    print(f"可用行业模板：{list_industries()}")
    print("── 结构校验 ──")
    for ind in industries:
        check_schema(ind)

    print("── 注入演练（bootstrap_industry）──")
    for ind in industries:
        s = bootstrap_industry(ind, tenant_id="default")
        print(f"  → {ind}: {s}")


if __name__ == "__main__":
    asyncio.run(main())
