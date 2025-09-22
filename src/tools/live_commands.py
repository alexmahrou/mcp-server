from __future__ import annotations

import json
from typing import Any, Dict, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class LiveCommandResult(TypedDict, total=False):
    projectId: int
    organizationId: str
    commandType: str
    raw: Dict[str, Any]


def _parse_project_id(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _load_command(command_json: str) -> Dict[str, Any] | None:
    try:
        payload = json.loads(command_json)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        return None
    return None


def register_live_trading_command_tools(mcp):
    @mcp.tool(annotations={"title": "Create live command"})
    async def create_live_command(projectId: str, commandJson: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        command = _load_command(commandJson)
        if command is None:
            return error_result(
                "validation-error",
                "commandJson must be valid JSON",
                "Provide the live command as a JSON string.",
            )

        payload = {"projectId": project_id, "command": command}

        def transform(data: Dict[str, Any]) -> LiveCommandResult:
            return LiveCommandResult(
                projectId=project_id,
                commandType=str(command.get("$type") or command.get("type") or ""),
                raw=data,
            )

        return await execute_api_call("/live/commands/create", payload, transform=transform)

    register_tool_contract("create_live_command", create_live_command, mcp)

    @mcp.tool(annotations={"title": "Broadcast live command"})
    async def broadcast_live_command(
        organizationId: str,
        commandJson: str,
        excludeProjectId: str,
    ) -> ToolResult:
        if not organizationId.strip():
            return error_result(
                "validation-error",
                "organizationId is required",
                "Provide the QuantConnect organization id.",
            )
        command = _load_command(commandJson)
        if command is None:
            return error_result(
                "validation-error",
                "commandJson must be valid JSON",
                "Provide the live command as a JSON string.",
            )

        payload: Dict[str, Any] = {"organizationId": organizationId, "command": command}
        excluded_project_id: int | None = None
        if excludeProjectId:
            project_id = _parse_project_id(excludeProjectId)
            if project_id is None:
                return error_result(
                    "validation-error",
                    "excludeProjectId must be numeric",
                    "Provide the project id to exclude as a stringified integer.",
                )
            payload["excludeProjectId"] = project_id
            excluded_project_id = project_id

        def transform(data: Dict[str, Any]) -> LiveCommandResult:
            result = LiveCommandResult(
                organizationId=organizationId,
                commandType=str(command.get("$type") or command.get("type") or ""),
                raw=data,
            )
            if excluded_project_id is not None:
                result["projectId"] = excluded_project_id
            return result

        return await execute_api_call("/live/commands/broadcast", payload, transform=transform)

    register_tool_contract(
        "broadcast_live_command",
        broadcast_live_command,
        mcp,
        defaults={"excludeProjectId": ""},
    )
