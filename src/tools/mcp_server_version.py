from __future__ import annotations

from typing import Any, Dict

import httpx

from __init__ import __version__
from tool_contract import register_tool_contract, ToolResult, error_result, success_result


def register_mcp_server_version_tools(mcp):
    @mcp.tool(
        annotations={"title": "Read QC MCP Server version", "readOnlyHint": True}
    )
    async def read_mcp_server_version() -> ToolResult:
        return success_result({"version": __version__, "source": "local"})

    register_tool_contract("read_mcp_server_version", read_mcp_server_version, mcp, safe=True)

    @mcp.tool(
        annotations={"title": "Read latest QC MCP Server version", "readOnlyHint": True}
    )
    async def read_latest_mcp_server_version() -> ToolResult:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://hub.docker.com/v2/namespaces/quantconnect/repositories/mcp-server/tags",
                    params={"page_size": 2},
                    timeout=10.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return error_result(
                    "api-http-error",
                    f"HTTP {exc.response.status_code}: {exc.response.text}",
                    "Retry later or check Docker Hub availability.",
                )
            except httpx.RequestError as exc:
                return error_result("api-request-error", str(exc), "Verify network connectivity.")

        payload: Dict[str, Any]
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        results = payload.get("results")
        version = ""
        if isinstance(results, list) and len(results) > 1:
            version = str(results[1].get("name") or "") if isinstance(results[1], dict) else ""
        elif isinstance(results, list) and results:
            version = str(results[0].get("name") or "") if isinstance(results[0], dict) else ""

        return success_result({"version": version, "source": "docker"})

    register_tool_contract("read_latest_mcp_server_version", read_latest_mcp_server_version, mcp, safe=False)
