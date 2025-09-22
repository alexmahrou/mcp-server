from __future__ import annotations

from typing import Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class CompileJobData(TypedDict, total=False):
    compileId: str
    projectId: int
    state: str
    parameterCount: int


class CompileReadData(TypedDict):
    compileId: str
    state: str
    logs: List[str]
    logCount: int


def _to_int(value: str, field: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def register_compile_tools(mcp):
    @mcp.tool(annotations={"title": "Create compile", "destructiveHint": False})
    async def create_compile(projectId: str) -> ToolResult:
        project_id_int = _to_int(projectId, "projectId")
        if project_id_int is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = {"projectId": project_id_int}

        def transform(data: Dict[str, object]) -> CompileJobData:
            parameters = data.get("parameters")
            parameter_count = len(parameters) if isinstance(parameters, list) else 0
            project_id = data.get("projectId")
            try:
                project_id_value = int(project_id) if project_id is not None else project_id_int
            except (TypeError, ValueError):
                project_id_value = project_id_int
            return CompileJobData(
                compileId=str(data.get("compileId") or ""),
                projectId=project_id_value,
                state=str(data.get("state") or ""),
                parameterCount=parameter_count,
            )

        return await execute_api_call("/compile/create", payload, transform=transform)

    register_tool_contract("create_compile", create_compile, mcp)

    @mcp.tool(annotations={"title": "Read compile", "readOnlyHint": True})
    async def read_compile(projectId: str, compileId: str) -> ToolResult:
        project_id_int = _to_int(projectId, "projectId")
        if project_id_int is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not compileId:
            return error_result(
                "validation-error",
                "compileId is required",
                "Provide the compile id returned from create_compile.",
            )

        payload = {"projectId": project_id_int, "compileId": compileId}

        def transform(data: Dict[str, object]) -> CompileReadData:
            logs_raw = data.get("logs")
            logs = [str(item) for item in logs_raw] if isinstance(logs_raw, list) else []
            return CompileReadData(
                compileId=str(data.get("compileId") or compileId),
                state=str(data.get("state") or ""),
                logs=logs,
                logCount=len(logs),
            )

        return await execute_api_call("/compile/read", payload, transform=transform)

    register_tool_contract("read_compile", read_compile, mcp)
