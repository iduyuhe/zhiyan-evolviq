"""MCP协议服务器——Agent工具调用入口（能力层联邦）

将 11 个 Agent 的 in-process 工具经统一命名空间暴露为标准 MCP 协议接口，
外部系统可经 MCP Client 调用任一 Agent 能力。Agent 内部仍走 in-process 主路径，
与 T4 收敛一致，零运行时风险。

兼容：保留原供应链6个短名工具（get_bom 等）作为别名，避免破坏既有 MCP 客户端。
"""

import json
import logging

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from src.agents.supply_chain.tools import SupplyChainTools
from src.runtime.mcp.federation import list_tools_specs, dispatch

logger = logging.getLogger(__name__)

server = Server("zhiyan-tools")
legacy_tools = SupplyChainTools()

# 旧版短名 -> 联邦命名空间（前5个可直转；supply_check 为组合动作，特殊处理）
_LEGACY_ALIASES = {
    "get_bom": "supply_chain__get_bom",
    "get_inventory": "supply_chain__get_inventory",
    "get_po": "supply_chain__get_po",
    "find_alternatives": "supply_chain__find_alternatives",
    "lock_inventory": "supply_chain__lock_inventory",
}


def _param_type_to_schema(python_type: str) -> dict:
    """将 federation 参数类型字符串转为 JSON Schema。"""
    if python_type == "array":
        return {"type": "array", "items": {"type": "string"}}
    if python_type == "number":
        return {"type": "number"}
    if python_type == "integer":
        return {"type": "integer"}
    return {"type": "string"}


def _build_input_schema(params: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            name: _param_type_to_schema(ptype) for name, ptype in params.items()
        },
    }


# 旧版6工具的简短 schema（向后兼容既有 MCP 客户端）
_LEGACY_SCHEMAS = {
    "get_bom": {"bom_id": {"type": "string"}},
    "get_inventory": {"material_codes": {"type": "array", "items": {"type": "string"}}},
    "get_po": {"material_codes": {"type": "array", "items": {"type": "string"}}},
    "find_alternatives": {
        "material_code": {"type": "string"},
        "max_price_variation_pct": {"type": "number"},
    },
    "lock_inventory": {
        "material_code": {"type": "string"},
        "qty": {"type": "integer"},
        "session_id": {"type": "string"},
    },
    "supply_check": {"bom_id": {"type": "string"}},
}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """注册所有可用工具：38 个联邦命名空间工具 + 6 个旧版别名。"""
    tool_list: list[types.Tool] = []
    for spec in list_tools_specs():
        tool_list.append(
            types.Tool(
                name=spec["name"],
                description=f"[{spec['agent']}] {spec['description']}",
                inputSchema=_build_input_schema(spec["params"]),
            )
        )
    # 旧版短名别名
    for name, schema in _LEGACY_SCHEMAS.items():
        tool_list.append(
            types.Tool(
                name=name,
                description=f"[supply_chain] 兼容别名：{name}",
                inputSchema={"type": "object", "properties": schema},
            )
        )
    return tool_list


async def _run_legacy_composite(name: str, arguments: dict) -> dict:
    """处理旧版组合动作 supply_check（无对应联邦单工具）。"""
    if name == "supply_check":
        bom = await legacy_tools.get_bom_data(arguments["bom_id"])
        material_codes = [item["material_code"] for item in bom["items"]]
        inventory = await legacy_tools.get_inventory(material_codes)
        pos = await legacy_tools.get_po_data(material_codes)
        return {
            "bom": bom["product_name"],
            "total_items": len(bom["items"]),
            "inventory": inventory,
            "pos": pos,
        }
    raise ValueError(f"Unknown legacy tool: {name}")


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """处理Agent的MCP工具调用请求（联邦 + 兼容别名）"""
    if not arguments:
        arguments = {}

    try:
        # 1) 联邦命名空间工具
        try:
            result = await dispatch(name, arguments)
        except ValueError:
            # 2) 旧版短名别名
            if name in _LEGACY_ALIASES:
                result = await dispatch(_LEGACY_ALIASES[name], arguments)
            elif name == "supply_check":
                result = await _run_legacy_composite(name, arguments)
            else:
                raise ValueError(f"Unknown MCP tool: {name}")

        return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    except Exception as e:
        logger.error(f"MCP tool {name} failed: {e}")
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, ensure_ascii=False))]


async def run_mcp_server():
    """启动MCP Server"""
    logger.info("🚀 MCP Federation Server starting on stdio transport...")
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="zhiyan-tools",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    import anyio
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    anyio.run(run_mcp_server)
