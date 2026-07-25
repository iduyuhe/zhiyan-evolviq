"""经验记忆检索（MemoryStore）——让 Agent 推理时能读回历史经验（记忆闭环）。

闭环链路：
    Agent 执行 → apply_execution_result / apply_orchestration_result 写 Insight 节点
        ↓
    Agent 下次推理 → recall(goal) 查回相关 Insight（按关键词相关度排序）
        ↓
    推理带上了"历史经验"，产出新结论 → 再次写回 Insight

设计（呼应「韧性降级」铁律）：
- 底层复用 neo4j_client 原语（Neo4j / 内存图双模式），图谱不可用时安全返回空。
- recall 纯只读、零副作用；任何异常都不外溢，绝不阻断推理。
- 相关度用轻量启发式（CJK 短语 + 子串重叠），不依赖 LLM，确定性、低延迟。
"""
from __future__ import annotations

import logging
import re
from typing import Any

from src.common import neo4j_client as neo

logger = logging.getLogger(__name__)

_CJK_RUN = re.compile(r"[一-鿿]+")


def _cjk_ngrams(text: str, ns=(2, 3)) -> list[str]:
    """抽取 CJK 字符 n-gram（二元/三元），用于中文部分重叠相关度匹配。"""
    grams: list[str] = []
    for run in _CJK_RUN.findall(text or ""):
        for n in ns:
            for i in range(len(run) - n + 1):
                grams.append(run[i:i + n])
    return grams


def _extract_terms(text: str) -> list[str]:
    """抽取匹配词：CJK n-gram（2/3 元）+ 英文/数字词。"""
    terms: list[str] = []
    terms.extend(_cjk_ngrams(text))
    for m in re.findall(r"[A-Za-z0-9_]{2,}", text or ""):
        terms.append(m.lower())
    return terms


def _score(goal: str, insight_text: str) -> int:
    """启发式相关度：双向子串命中 + CJK n-gram 重叠计数。

    中文无空格，整句无法做词匹配；改用字符 n-gram 重叠，
    使"光刻机套刻偏差"与"光刻机偏移导致套刻偏差"能命中共同片段。
    """
    score = 0
    g = (goal or "").lower()
    it = (insight_text or "").lower()
    if not g or not it:
        return 0
    if g in it or it in g:
        score += 3
    goal_terms = _extract_terms(g)
    it_terms = set(_extract_terms(it))
    score += sum(1 for t in goal_terms if t in it_terms)
    return score


async def recall(goal: str, tenant_id: str = "default", limit: int = 5) -> dict:
    """按目标召回相关历史经验。

    Returns:
        {"insights": [str, ...], "entities": [{"id","labels","props"}, ...]}
        - insights: 相关 Insight 文本（按相关度降序，最多 limit 条）
        - entities: 与目标关键词相关的实体节点（可选，供深度推理）
    """
    try:
        if not neo.neo_available:
            return {"insights": [], "entities": []}

        nodes = await neo.query_nodes("Insight", tenant=tenant_id)
        if not nodes:
            return {"insights": [], "entities": []}

        scored = []
        for n in nodes:
            text = n.get("props", {}).get("text", "")
            s = _score(goal, text)
            if s > 0:
                scored.append((s, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        insights = [t for _, t in scored[:limit]]

        # 实体召回：取与目标 term 相关的 Material/Equipment/Product 等（轻量）
        entities: list[dict] = []
        terms = _extract_terms(goal)
        if terms:
            for label in ("Material", "Equipment", "Product", "DefectCase", "Line"):
                for cand in await neo.query_nodes(label, tenant=tenant_id):
                    props = cand.get("props", {})
                    hay = " ".join(str(v) for v in props.values())
                    if any(t in hay.lower() for t in terms if len(t) >= 2):
                        entities.append({"id": cand.get("id"), "labels": cand.get("labels"), "props": props})
                        if len(entities) >= limit:
                            break
                if len(entities) >= limit:
                    break

        return {"insights": insights, "entities": entities}
    except Exception as e:
        logger.warning(f"记忆召回失败（降级为空）：{e}")
        return {"insights": [], "entities": []}


async def recall_for_goal(goal: str, tenant_id: str = "default", limit: int = 5) -> dict:
    """recall 的别名（编排器调用，语义更明确）。"""
    return await recall(goal, tenant_id=tenant_id, limit=limit)
