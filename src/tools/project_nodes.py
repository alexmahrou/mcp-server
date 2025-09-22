from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class NodeInfo(TypedDict, total=False):
    id: str
    sku: str
    name: str
    active: bool
    busy: bool
    cpu: int
    ram: float
    hasGpu: int


class ProjectNodesData(TypedDict):
    projectId: int
    autoSelect: bool
    backtest: List[NodeInfo]
    live: List[NodeInfo]
    research: List[NodeInfo]


def _parse_project_id(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_nodes(project_id: int, payload: Dict[str, Any]) -> ProjectNodesData:
    nodes_payload = payload.get("nodes")
    categories = {"backtest": [], "live": [], "research": []}
    if isinstance(nodes_payload, dict):
        for category in categories.keys():
            raw_nodes = nodes_payload.get(category)
            if not isinstance(raw_nodes, list):
                continue
            for node in raw_nodes:
                if not isinstance(node, dict):
                    continue
                categories[category].append(
                    NodeInfo(
                        id=str(node.get("id") or ""),
                        sku=str(node.get("sku") or ""),
                        name=str(node.get("name") or ""),
                        active=bool(node.get("active") or False),
                        busy=bool(node.get("busy") or False),
                        cpu=int(node.get("cpu") or 0),
                        ram=float(node.get("ram") or 0.0),
                        hasGpu=int(node.get("hasGpu") or 0),
                    )
                )
    auto_select = bool(payload.get("autoSelectNode") or False)
    return ProjectNodesData(
        projectId=project_id,
        autoSelect=auto_select,
        backtest=categories["backtest"],
        live=categories["live"],
        research=categories["research"],
    )


def register_project_node_tools(mcp):
    @mcp.tool(annotations={"title": "Read project nodes", "readOnlyHint": True})
    async def read_project_nodes(projectId: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = {"projectId": project_id}

        def transform(data: Dict[str, Any]) -> ProjectNodesData:
            return _normalize_nodes(project_id, data)

        return await execute_api_call("/projects/nodes/read", payload, transform=transform)

    register_tool_contract("read_project_nodes", read_project_nodes, mcp, safe=False)

    @mcp.tool(
        annotations={
            "title": "Update project nodes",
            "destructiveHint": False,
            "idempotentHint": True,
        }
    )
    async def update_project_nodes(projectId: str, nodes: List[str]) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload: Dict[str, Any] = {"projectId": project_id}
        if nodes:
            payload["nodes"] = nodes

        def transform(data: Dict[str, Any]) -> ProjectNodesData:
            return _normalize_nodes(project_id, data)

        return await execute_api_call("/projects/nodes/update", payload, transform=transform)

    register_tool_contract("update_project_nodes", update_project_nodes, mcp, defaults={"nodes": []})
