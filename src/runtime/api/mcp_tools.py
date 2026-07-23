"""MCP工具路由——将Agent工具暴露为HTTP API

设计分层（与 T4 收敛一致）：
- 兼容层 /mcp/tools + /mcp/tools/{tool}/call：保留原供应链6工具契约，集成测试依赖 len==6。
- 联邦层 /mcp/federation*：经统一命名空间暴露全部 11 Agent 共 38 个 in-process 工具，
  外部系统可经 MCP 协议调用任一 Agent 能力；Agent 内部仍走 in-process 主路径。

事实锚点铁律：仅透传调用确定性工具，绝不改写任何业务数字或动作。
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from src.agents.supply_chain.tools import SupplyChainTools
from src.runtime.mcp.federation import (
    list_tools_specs,
    federation_summary,
    dispatch,
)
from src.runtime.api.deps import get_tenant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["mcp-tools"])

tools = SupplyChainTools()


class ToolCallRequest(BaseModel):
    arguments: dict = {}


# ---------------------------------------------------------------------------
# 兼容层：供应链6工具（不动，集成测试 test_full_flow 断言 len(tools)==6）
# ---------------------------------------------------------------------------
_LEGACY_REGISTRY = {
    "get_bom": {
        "description": "获取BOM物料清单数据",
        "params": {"bom_id": "string"},
    },
    "get_inventory": {
        "description": "查询物料库存",
        "params": {"material_codes": "array"},
    },
    "get_po": {
        "description": "查询采购订单",
        "params": {"material_codes": "array"},
    },
    "find_alternatives": {
        "description": "查找替代料方案",
        "params": {"material_code": "string", "max_price_variation_pct": "number"},
    },
    "lock_inventory": {
        "description": "锁定库存（需授权）",
        "params": {"material_code": "string", "qty": "integer", "session_id": "string"},
    },
    "supply_check": {
        "description": "执行BOM齐套检查",
        "params": {"bom_id": "string"},
    },
}


@router.get("/tools")
async def list_tools():
    """列出所有可用工具（MCP list_tools协议兼容，供应链6工具）"""
    return {
        "tools": [
            {"name": name, "description": info["description"], "params": info["params"]}
            for name, info in _LEGACY_REGISTRY.items()
        ]
    }


@router.post("/tools/{tool_name}/call")
async def call_tool(tool_name: str, req: ToolCallRequest, tenant: str = Depends(get_tenant)):
    """调用指定工具（MCP call_tool协议兼容，供应链6工具）"""
    args = req.arguments
    logger.info(f"MCP call: {tool_name}({args}) tenant={tenant}")

    try:
        if tool_name == "get_bom":
            result = await tools.get_bom_data(args["bom_id"])
        elif tool_name == "get_inventory":
            result = await tools.get_inventory(args.get("material_codes", []))
        elif tool_name == "get_po":
            result = await tools.get_po(args.get("material_codes", []))
        elif tool_name == "find_alternatives":
            result = await tools.find_alternatives(
                args["material_code"],
                args.get("max_price_variation_pct", 5.0),
            )
        elif tool_name == "lock_inventory":
            result = await tools.lock_inventory(
                args["material_code"],
                args["qty"],
                args.get("session_id", "unknown"),
            )
        elif tool_name == "supply_check":
            bom = await tools.get_bom_data(args["bom_id"])
            codes = [i["material_code"] for i in bom["items"]]
            inv = await tools.get_inventory(codes)
            pos = await tools.get_po_data(codes)
            result = {"bom": bom["product_name"], "items": bom["items"], "inventory": inv, "pos": pos}
        else:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

        return {"tenant_id": tenant, "tool": tool_name, "result": result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 联邦层：11 Agent 能力暴露（能力层联邦，由 federation 驱动）
# ---------------------------------------------------------------------------
@router.get("/federation")
async def get_federation():
    """联邦全景：按 Agent 分组的 38 个工具清单。"""
    return federation_summary()


@router.get("/federation/tools")
async def list_federation_tools():
    """联邦工具扁平清单（38 个，{agent}__{method} 命名空间）。"""
    return {"tools": list_tools_specs()}


@router.post("/federation/{tool_name}/call")
async def call_federation_tool(tool_name: str, req: ToolCallRequest, tenant: str = Depends(get_tenant)):
    """调用联邦工具，tool_name 形如 supply_chain__get_bom。"""
    logger.info(f"MCP federation call: {tool_name}({req.arguments}) tenant={tenant}")
    try:
        result = await dispatch(tool_name, req.arguments, tenant_id=tenant)
        return {"tenant_id": tenant, "tool": tool_name, "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
