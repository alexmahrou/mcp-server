from __future__ import annotations

from typing import Dict, List, TypedDict

from code_source_id import add_code_source_id
from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class FileDetail(TypedDict):
    projectId: int
    name: str
    content: str
    bytes: int


class FileListData(TypedDict):
    projectId: int
    files: List[FileDetail]
    count: int


class FileOperationData(TypedDict):
    projectId: int
    name: str
    message: str


def _parse_project_id(projectId: str) -> int | None:
    try:
        return int(projectId)
    except (TypeError, ValueError):
        return None


def _build_file_detail(project_id: int, file_payload: Dict[str, object]) -> FileDetail:
    name = str(file_payload.get("name") or "")
    content = str(file_payload.get("content") or "")
    return FileDetail(
        projectId=project_id,
        name=name,
        content=content,
        bytes=len(content.encode("utf-8")),
    )


def register_file_tools(mcp):
    @mcp.tool(
        annotations={"title": "Create file", "destructiveHint": False, "idempotentHint": True}
    )
    async def create_file(projectId: str, name: str, content: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not name:
            return error_result("validation-error", "name is required", "Set the file name to create.")

        payload = add_code_source_id({"projectId": project_id, "name": name, "content": content})

        def transform(_: Dict[str, object]) -> FileOperationData:
            return FileOperationData(projectId=project_id, name=name, message="File created")

        return await execute_api_call("/files/create", payload, transform=transform)

    register_tool_contract("create_file", create_file, mcp)

    @mcp.tool(annotations={"title": "Read file", "readOnlyHint": True})
    async def read_file(projectId: str, name: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )

        payload = add_code_source_id({"projectId": project_id})
        if name:
            payload["name"] = name

        def transform(data: Dict[str, object]) -> FileListData:
            files_data = []
            files = data.get("files")
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, dict):
                        files_data.append(_build_file_detail(project_id, item))
            if not files_data and name:
                # Provide context even when API returned no content.
                files_data.append(
                    FileDetail(projectId=project_id, name=name, content="", bytes=0)
                )
            return FileListData(projectId=project_id, files=files_data, count=len(files_data))

        return await execute_api_call("/files/read", payload, transform=transform)

    register_tool_contract("read_file", read_file, mcp, defaults={"name": ""})

    @mcp.tool(annotations={"title": "Update file name", "idempotentHint": True})
    async def update_file_name(projectId: str, name: str, newName: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not name or not newName:
            return error_result(
                "validation-error",
                "Current and new file names are required",
                "Provide both name and newName values.",
            )

        payload = add_code_source_id({
            "projectId": project_id,
            "name": name,
            "newName": newName,
        })

        def transform(_: Dict[str, object]) -> FileOperationData:
            return FileOperationData(projectId=project_id, name=newName, message="File renamed")

        return await execute_api_call("/files/update", payload, transform=transform)

    register_tool_contract("update_file_name", update_file_name, mcp)

    @mcp.tool(annotations={"title": "Update file contents", "idempotentHint": True})
    async def update_file_contents(projectId: str, name: str, content: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not name:
            return error_result("validation-error", "name is required", "Provide the file name to update.")

        payload = add_code_source_id({
            "projectId": project_id,
            "name": name,
            "content": content,
        })

        def transform(_: Dict[str, object]) -> FileDetail:
            return _build_file_detail(project_id, {"name": name, "content": content})

        return await execute_api_call("/files/update", payload, transform=transform)

    register_tool_contract("update_file_contents", update_file_contents, mcp)

    @mcp.tool(annotations={"title": "Patch file", "idempotentHint": True})
    async def patch_file(projectId: str, patch: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not patch:
            return error_result("validation-error", "patch is required", "Provide a unified diff patch string.")

        payload = add_code_source_id({"projectId": project_id, "patch": patch})

        def transform(_: Dict[str, object]) -> FileOperationData:
            return FileOperationData(projectId=project_id, name="", message="Patch applied")

        return await execute_api_call("/files/patch", payload, transform=transform)

    register_tool_contract("patch_file", patch_file, mcp)

    @mcp.tool(annotations={"title": "Delete file", "idempotentHint": True})
    async def delete_file(projectId: str, name: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Pass the project id as a stringified integer.",
            )
        if not name:
            return error_result("validation-error", "name is required", "Provide the file name to delete.")

        payload = add_code_source_id({"projectId": project_id, "name": name})

        def transform(_: Dict[str, object]) -> FileOperationData:
            return FileOperationData(projectId=project_id, name=name, message="File deleted")

        return await execute_api_call("/files/delete", payload, transform=transform)

    register_tool_contract("delete_file", delete_file, mcp)
