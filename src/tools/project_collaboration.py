from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from code_source_id import add_code_source_id
from tool_contract import register_tool_contract, ToolResult, error_result, success_result
from tool_helpers import execute_api_call


class CollaboratorRecord(TypedDict, total=False):
    userId: str
    liveControl: bool
    write: bool
    owner: bool
    email: str
    name: str


class CollaboratorListData(TypedDict):
    projectId: int
    collaborators: List[CollaboratorRecord]
    count: int


class CollaboratorUpdateData(TypedDict, total=False):
    projectId: int
    collaboratorUserId: str
    liveControl: bool
    write: bool
    message: str


def _parse_project_id(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _normalize_collaborators(project_id: int, payload: Dict[str, Any]) -> CollaboratorListData:
    collaborators_raw = payload.get("collaborators")
    collaborators: List[CollaboratorRecord] = []
    if isinstance(collaborators_raw, list):
        for entry in collaborators_raw:
            if not isinstance(entry, dict):
                continue
            collaborators.append(
                CollaboratorRecord(
                    userId=str(entry.get("publicId") or entry.get("uid") or ""),
                    liveControl=bool(entry.get("liveControl") or entry.get("collaborationLiveControl") or False),
                    write=bool(entry.get("permission") == "write" or entry.get("collaborationWrite") or entry.get("write")),
                    owner=bool(entry.get("owner") or False),
                    email=str(entry.get("email") or ""),
                    name=str(entry.get("name") or ""),
                )
            )
    return CollaboratorListData(
        projectId=project_id,
        collaborators=collaborators,
        count=len(collaborators),
    )


def register_project_collaboration_tools(mcp):
    @mcp.tool(
        annotations={
            "title": "Create project collaborator",
            "destructiveHint": False,
            "idempotentHint": True,
        }
    )
    async def create_project_collaborator(
        projectId: str,
        collaboratorUserId: str,
        collaborationLiveControl: bool,
        collaborationWrite: bool,
    ) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not collaboratorUserId:
            return error_result(
                "validation-error",
                "collaboratorUserId is required",
                "Provide the collaborator's public id.",
            )

        payload = {
            "projectId": project_id,
            "collaboratorUserId": collaboratorUserId,
            "collaborationLiveControl": bool(collaborationLiveControl),
            "collaborationWrite": bool(collaborationWrite),
        }

        def transform(data: Dict[str, Any]) -> CollaboratorListData:
            return _normalize_collaborators(project_id, data)

        return await execute_api_call("/projects/collaboration/create", payload, transform=transform)

    register_tool_contract("create_project_collaborator", create_project_collaborator, mcp)

    @mcp.tool(
        annotations={"title": "Read project collaborators", "readOnlyHint": True}
    )
    async def read_project_collaborators(projectId: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = {"projectId": project_id}

        def transform(data: Dict[str, Any]) -> CollaboratorListData:
            return _normalize_collaborators(project_id, data)

        return await execute_api_call("/projects/collaboration/read", payload, transform=transform)

    register_tool_contract("read_project_collaborators", read_project_collaborators, mcp, safe=False)

    @mcp.tool(
        annotations={"title": "Update project collaborator", "idempotentHint": True}
    )
    async def update_project_collaborator(
        projectId: str,
        collaboratorUserId: str,
        liveControl: bool,
        write: bool,
    ) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not collaboratorUserId:
            return error_result(
                "validation-error",
                "collaboratorUserId is required",
                "Provide the collaborator's public id.",
            )

        payload = {
            "projectId": project_id,
            "collaboratorUserId": collaboratorUserId,
            "liveControl": bool(liveControl),
            "write": bool(write),
        }

        def transform(data: Dict[str, Any]) -> CollaboratorListData:
            return _normalize_collaborators(project_id, data)

        return await execute_api_call("/projects/collaboration/update", payload, transform=transform)

    register_tool_contract("update_project_collaborator", update_project_collaborator, mcp)

    @mcp.tool(
        annotations={"title": "Delete project collaborator", "idempotentHint": True}
    )
    async def delete_project_collaborator(projectId: str, collaboratorId: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not collaboratorId:
            return error_result(
                "validation-error",
                "collaboratorId is required",
                "Provide the collaborator's id to remove.",
            )

        payload = {"projectId": project_id, "collaboratorId": collaboratorId}

        def transform(data: Dict[str, Any]) -> CollaboratorListData:
            return _normalize_collaborators(project_id, data)

        return await execute_api_call("/projects/collaboration/delete", payload, transform=transform)

    register_tool_contract("delete_project_collaborator", delete_project_collaborator, mcp)

    @mcp.tool(
        annotations={"title": "Lock project with collaborators", "idempotentHint": True}
    )
    async def lock_project_with_collaborators(projectId: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = add_code_source_id({"projectId": project_id})
        response = await execute_api_call(
            "/projects/collaboration/lock/acquire",
            payload,
            transform=lambda data: {"projectId": project_id, "status": str(data.get("status") or "locked")},
        )

        # lock acquire returns empty JSON when successful; ensure standard format
        if response["success"]:
            return success_result({"projectId": project_id, "status": "locked"})
        return response

    register_tool_contract("lock_project_with_collaborators", lock_project_with_collaborators, mcp)
