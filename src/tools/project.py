from __future__ import annotations

from typing import Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class ProjectSummary(TypedDict):
    projectId: int
    name: str
    language: str
    description: str


class ProjectListData(TypedDict, total=False):
    projects: List[ProjectSummary]
    count: int


class ProjectOperationData(TypedDict, total=False):
    projectId: int
    message: str


def _normalize_projects(payload: Dict[str, object]) -> ProjectListData:
    projects_raw = payload.get("projects")
    projects: List[ProjectSummary] = []

    if isinstance(projects_raw, list):
        for item in projects_raw:
            if not isinstance(item, dict):
                continue
            project_id = item.get("projectId")
            try:
                project_id_int = int(project_id)
            except (TypeError, ValueError):
                project_id_int = 0
            projects.append(
                ProjectSummary(
                    projectId=project_id_int,
                    name=str(item.get("name") or ""),
                    language=str(item.get("language") or ""),
                    description=str(item.get("description") or ""),
                )
            )

    return ProjectListData(projects=projects, count=len(projects))


def _normalize_rest_response(payload: Dict[str, object]) -> ProjectOperationData:
    project_id = payload.get("projectId")
    try:
        project_id_int = int(project_id) if project_id is not None else 0
    except (TypeError, ValueError):
        project_id_int = 0
    message = str(payload.get("message") or payload.get("result") or "")
    return ProjectOperationData(projectId=project_id_int, message=message)


def register_project_tools(mcp):
    @mcp.tool(
        annotations={
            "title": "Create project",
            "destructiveHint": False,
            "idempotentHint": False,
        }
    )
    async def create_project(name: str, language: str) -> ToolResult:
        payload = {"name": name, "language": language}
        return await execute_api_call("/projects/create", payload, transform=_normalize_projects)

    register_tool_contract("create_project", create_project, mcp)

    @mcp.tool(annotations={"title": "Read project", "readOnlyHint": True})
    async def read_project(projectId: str, start: str, end: str) -> ToolResult:
        if not projectId and not start and not end:
            return error_result(
                "validation-error",
                "Provide a projectId or start/end range to fetch projects.",
                "Set projectId to the target project or use start/end pagination values.",
            )

        payload: Dict[str, object] = {}
        if projectId:
            try:
                payload["projectId"] = int(projectId)
            except ValueError:
                return error_result("validation-error", "projectId must be numeric", "Pass the project id as a stringified integer.")
        if start:
            payload["start"] = start
        if end:
            payload["end"] = end

        return await execute_api_call("/projects/read", payload, transform=_normalize_projects)

    register_tool_contract(
        "read_project",
        read_project,
        mcp,
        defaults={"projectId": "", "start": "", "end": ""},
    )

    @mcp.tool(annotations={"title": "List projects", "readOnlyHint": True})
    async def list_projects() -> ToolResult:
        return await execute_api_call("/projects/read", {}, transform=_normalize_projects)

    register_tool_contract("list_projects", list_projects, mcp, safe=False)

    @mcp.tool(annotations={"title": "Update project", "idempotentHint": True})
    async def update_project(projectId: str, name: str, description: str) -> ToolResult:
        try:
            project_id_int = int(projectId)
        except ValueError:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        if not name and not description:
            return error_result(
                "validation-error",
                "Provide at least one field to update.",
                "Set name and/or description to update the project.",
            )

        payload: Dict[str, object] = {"projectId": project_id_int}
        if name:
            payload["name"] = name
        if description:
            payload["description"] = description

        return await execute_api_call("/projects/update", payload, transform=_normalize_rest_response)

    register_tool_contract(
        "update_project",
        update_project,
        mcp,
        defaults={"name": "", "description": ""},
    )

    @mcp.tool(annotations={"title": "Delete project", "idempotentHint": True})
    async def delete_project(projectId: str) -> ToolResult:
        try:
            project_id_int = int(projectId)
        except ValueError:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = {"projectId": project_id_int}
        return await execute_api_call("/projects/delete", payload, transform=_normalize_rest_response)

    register_tool_contract("delete_project", delete_project, mcp)
