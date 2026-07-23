"""Neo4j 知识图谱连接管理——韧性化（借鉴 db.py 模式）

设计要点：
1. 生产目标为 Neo4j（config.neo4j_uri，Bolt 协议）。
2. Neo4j 不可达（沙箱未起 docker）或 driver 未安装时，自动回退到内存图
   （dict 邻接表），图操作原语在两种模式行为一致，保证「图谱能力」不丢失。
3. init_neo4j() 失败则置 neo_available=False，图谱层全面降级为 no-op。
4. neo4j driver 延迟导入：未安装/不可达均不抛 ImportError 中断启动。
5. 提供统一的图操作原语（merge_node/merge_edge/get_neighbors/query_nodes/stats），
   上层 knowledge_graph.py 只依赖原语，与底层存储无关。
"""

import logging
from typing import Optional

from src.common.config import settings

logger = logging.getLogger(__name__)

driver = None
neo_available: bool = False
neo_mode: str = "none"  # "neo4j" | "memory" | "none"

# ---- 内存图回退（dict 邻接表）----
_memory_nodes: dict = {}   # node_id -> {"labels": set, "props": dict}
_memory_edges: list = []   # [{"from": id, "to": id, "type": str, "props": dict}]


def configure_neo4j(uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None) -> None:
    """创建 Neo4j 异步 driver。失败则 driver=None（后续走内存回退）。"""
    global driver

    uri = uri or settings.neo4j_uri
    user = user or settings.neo4j_user
    password = password or settings.neo4j_password
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Neo4j driver 已创建（lazy，连接待 verify）：{uri}")
    except Exception as e:
        logger.warning(f"⚠️ Neo4j driver 不可用（{type(e).__name__}），将回退内存图：{e}")
        driver = None


async def init_neo4j() -> bool:
    """连通性探测。Neo4j 不可达自动回退内存图。返回 neo_available。"""
    global neo_available, neo_mode
    if driver is None:
        configure_neo4j()
    # 1) 试 Neo4j（仅当 driver 存在）
    if driver is not None:
        try:
            await driver.verify_connectivity()
            neo_available = True
            neo_mode = "neo4j"
            logger.info(f"✅ Neo4j 就绪 [{neo_mode}] {settings.neo4j_uri}")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Neo4j 不可达（{type(e).__name__}），回退内存图：{e}")
    # 2) 内存图回退
    neo_available = True
    neo_mode = "memory"
    logger.warning("⚠️ 已回退内存图（图谱可构建可查询，非生产 Neo4j）")
    return True


# ============ 图操作原语（统一接口，两种模式实现）============

async def merge_node(label: str, node_id: str, props: Optional[dict] = None) -> None:
    """创建/合并节点（label + 业务 id 唯一键）。"""
    props = props or {}
    if neo_mode == "neo4j" and driver is not None:
        try:
            await driver.execute_query(
                f"MERGE (n:`{label}` {{id:$id}}) SET n += $props",
                parameters_={"id": node_id, "props": props},
            )
            return
        except Exception as e:
            logger.warning(f"Neo4j merge_node 失败，转内存图：{e}")
    # 内存图
    node = _memory_nodes.setdefault(node_id, {"labels": set(), "props": {}})
    node["labels"].add(label)
    node["props"].update(props)


async def merge_edge(from_id: str, to_id: str, etype: str, props: Optional[dict] = None) -> None:
    """创建/合并关系（from_id/to_id 为全局 node_id）。"""
    props = props or {}
    if neo_mode == "neo4j" and driver is not None:
        try:
            q = (
                "MATCH (a {id:$from}), (b {id:$to}) "
                "MERGE (a)-[r:`" + etype + "`]->(b) SET r += $props"
            )
            await driver.execute_query(
                q, parameters_={"from": from_id, "to": to_id, "props": props}
            )
            return
        except Exception as e:
            logger.warning(f"Neo4j merge_edge 失败，转内存图：{e}")
    _memory_edges.append({"from": from_id, "to": to_id, "type": etype, "props": dict(props)})


async def get_node(node_id: str) -> Optional[dict]:
    if neo_mode == "neo4j" and driver is not None:
        try:
            rec = await driver.execute_query(
                "MATCH (n {id:$id}) RETURN n", parameters_={"id": node_id}
            )
            if rec.records:
                node = rec.records[0]["n"]
                return {"id": node_id, "labels": list(node.labels), "props": dict(node)}
        except Exception:
            pass
    node = _memory_nodes.get(node_id)
    if node:
        return {"id": node_id, "labels": list(node["labels"]), "props": node["props"]}
    return None


async def get_neighbors(node_id: str, edge: Optional[str] = None, direction: str = "out", tenant: Optional[str] = None) -> list[dict]:
    """返回邻居节点（含关系类型）。direction: out/in/any。tenant: 按租户隔离（仅返回该租户写入的关系）。"""
    result = []
    if neo_mode == "neo4j" and driver is not None:
        try:
            if direction == "out":
                q = "MATCH (a {id:$id})-[r]->(b) RETURN r, b"
            elif direction == "in":
                q = "MATCH (a {id:$id})<-[r]-(b) RETURN r, b"
            else:
                q = "MATCH (a {id:$id})-[r]-(b) RETURN r, b"
            if tenant:
                q = q.replace(" RETURN", " WHERE r.tenant = $p_tenant RETURN")
            rec = await driver.execute_query(q, parameters_={"id": node_id, "p_tenant": tenant} if tenant else {"id": node_id})
            for r in rec.records:
                rel, nb = r["r"], r["b"]
                if edge and rel.type != edge:
                    continue
                result.append(
                    {"id": nb["id"], "labels": list(nb.labels),
                     "props": dict(nb), "edge_type": rel.type, "edge_props": dict(rel)}
                )
            return result
        except Exception:
            pass
    # 内存图
    for e in _memory_edges:
        if edge and e["type"] != edge:
            continue
        if tenant and e["props"].get("tenant") != tenant:
            continue
        match = (direction in ("out", "any") and e["from"] == node_id) or \
                (direction in ("in", "any") and e["to"] == node_id)
        if not match:
            continue
        other = e["to"] if direction in ("out", "any") else e["from"]
        n = _memory_nodes.get(other)
        if n:
            result.append(
                {"id": other, "labels": list(n["labels"]),
                 "props": n["props"], "edge_type": e["type"], "edge_props": e["props"]}
            )
    return result


async def query_nodes(label: str, tenant: Optional[str] = None, **filters) -> list[dict]:
    """按 label + 属性过滤返回节点。tenant: 按租户隔离（仅返回该租户写入的节点）。"""
    if neo_mode == "neo4j" and driver is not None:
        try:
            where = " AND ".join(f"n.`{k}` = $p_{k}" for k in filters) if filters else ""
            if tenant:
                where = (where + " AND " if where else "") + "n.tenant = $p_tenant"
            q = f"MATCH (n:`{label}`)" + (f" WHERE {where}" if where else "") + " RETURN n"
            params = {f"p_{k}": v for k, v in filters.items()}
            if tenant:
                params["p_tenant"] = tenant
            rec = await driver.execute_query(q, parameters_=params)
            return [
                {"id": r["n"]["id"], "labels": list(r["n"].labels), "props": dict(r["n"])}
                for r in rec.records
            ]
        except Exception:
            pass
    # 内存图
    out = []
    for nid, n in _memory_nodes.items():
        if label not in n["labels"]:
            continue
        if tenant and n["props"].get("tenant") != tenant:
            continue
        if all(n["props"].get(k) == v for k, v in filters.items()):
            out.append({"id": nid, "labels": list(n["labels"]), "props": n["props"]})
    return out


async def clear_graph() -> None:
    global _memory_nodes, _memory_edges
    if neo_mode == "neo4j" and driver is not None:
        try:
            await driver.execute_query("MATCH (n) DETACH DELETE n")
        except Exception as e:
            logger.warning(f"Neo4j clear 失败：{e}")
    _memory_nodes = {}
    _memory_edges = []


async def graph_stats() -> dict:
    if neo_mode == "neo4j" and driver is not None:
        try:
            nrec = await driver.execute_query("MATCH (n) RETURN labels(n)[0] AS lbl, count(*) AS c")
            erec = await driver.execute_query("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c")
            nodes_by_label = {r["lbl"]: r["c"] for r in nrec.records}
            edges_by_type = {r["t"]: r["c"] for r in erec.records}
            return {
                "total_nodes": sum(nodes_by_label.values()),
                "total_edges": sum(edges_by_type.values()),
                "nodes_by_label": nodes_by_label,
                "edges_by_type": edges_by_type,
            }
        except Exception:
            pass
    nodes_by_label = {}
    for n in _memory_nodes.values():
        for lbl in n["labels"]:
            nodes_by_label[lbl] = nodes_by_label.get(lbl, 0) + 1
    edges_by_type = {}
    for e in _memory_edges:
        edges_by_type[e["type"]] = edges_by_type.get(e["type"], 0) + 1
    return {
        "total_nodes": len(_memory_nodes),
        "total_edges": len(_memory_edges),
        "nodes_by_label": nodes_by_label,
        "edges_by_type": edges_by_type,
    }


def neo_status() -> dict:
    """对外暴露图谱状态。"""
    return {"available": neo_available, "mode": neo_mode}
