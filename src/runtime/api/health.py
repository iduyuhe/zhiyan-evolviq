"""健康检查API + 生产级监控端点"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from src.common.db import db_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "智衍 EvolvIQ Runtime",
        "version": "0.1.0",
        "db": db_status(),
    }


@router.get("/health/detailed")
async def health_detailed():
    """生产级详细健康检查——聚合全部子系统状态。"""
    import datetime

    result: dict = {
        "status": "ok",
        "service": "智衍 EvolvIQ Runtime",
        "version": "0.1.0",
        "timestamp": datetime.datetime.now().isoformat(),
    }

    try:
        result["db"] = db_status()
    except Exception as e:
        result["db"] = {"available": False, "error": str(e)}
        result["status"] = "degraded"

    try:
        from src.gateways.manager import manager as gw
        result["gateways"] = await gw.health()
    except Exception as e:
        result["gateways"] = {"error": str(e)}

    try:
        from src.runtime.uns import uns as u
        result["uns"] = {"channels": len(u._events), "channel_counts": u.channel_counts()}
    except Exception as e:
        result["uns"] = {"error": str(e)}

    try:
        from src.common import neo4j_client as neo
        result["knowledge_graph"] = {"mode": neo.neo_mode if hasattr(neo, "neo_mode") else "unknown"}
    except Exception as e:
        result["knowledge_graph"] = {"error": str(e)}

    try:
        from src.runtime.tenant_store import tenant_store as ts
        result["tenants"] = {"count": len(ts.list())}
    except Exception as e:
        result["tenants"] = {"error": str(e)}

    try:
        from src.runtime.experience import experience as exp
        result["experience"] = {
            "total_records": len(exp._records),
            "tacit": len([r for r in exp._records if r.get("kind") == "tacit"]),
            "outcomes": len([r for r in exp._records if r.get("kind") == "outcome"]),
        }
    except Exception as e:
        result["experience"] = {"error": str(e)}

    try:
        from src.runtime.agent.router import AGENT_REGISTRY
        result["agents"] = {"count": len(AGENT_REGISTRY)}
    except Exception:
        result["agents"] = {"count": "unknown"}

    return result


@router.get("/health/metrics")
async def health_metrics():
    """生产 Prometheus 兼容 Metrics 端点。"""
    lines = [
        "# HELP zhiyan_agents_total Total number of registered agents",
        "# TYPE zhiyan_agents_total gauge",
    ]
    try:
        from src.runtime.agent.router import AGENT_REGISTRY
        lines.append(f"zhiyan_agents_total {len(AGENT_REGISTRY)}")
    except Exception:
        lines.append("zhiyan_agents_total 0")

    try:
        from src.runtime.experience import experience as exp
        lines.append("# HELP zhiyan_experience_records_total Total experience records")
        lines.append("# TYPE zhiyan_experience_records_total gauge")
        lines.append(f"zhiyan_experience_records_total {len(exp._records)}")
    except Exception:
        pass

    try:
        from src.runtime.uns import uns as u
        lines.append("# HELP zhiyan_uns_events_total Total UNS events")
        lines.append("# TYPE zhiyan_uns_events_total gauge")
        lines.append(f"zhiyan_uns_events_total {len(u._events)}")
    except Exception:
        pass

    try:
        from src.runtime.consequence import consequence as cq
        s = cq.stats()
        lines.append("# HELP zhiyan_consequences_total Total consequence records")
        lines.append("# TYPE zhiyan_consequences_total gauge")
        lines.append(f"zhiyan_consequences_total {s['total_consequences']}")
        lines.append(f"zhiyan_consequences_validated {s['validated']}")
        lines.append(f"zhiyan_consequences_contradicted {s['contradicted']}")
    except Exception:
        pass

    try:
        d = db_status()
        db_available = 1 if d.get("available") else 0
        lines.append("# HELP zhiyan_db_available Database availability (1=up)")
        lines.append("# TYPE zhiyan_db_available gauge")
        lines.append(f"zhiyan_db_available {db_available}")
    except Exception:
        pass

    lines.append("")
    return PlainTextResponse("\n".join(lines))
