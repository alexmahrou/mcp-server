from __future__ import annotations

from base64 import b64decode
from typing import Any, Dict, List, TypedDict

import httpx

from api_connection import BASE_URL, get_headers, post
from tool_contract import register_tool_contract, ToolResult, error_result, success_result
from tool_helpers import execute_api_call


class ObjectUploadResult(TypedDict, total=False):
    organizationId: str
    key: str
    bytes: int
    raw: Dict[str, Any]


class ObjectMetadata(TypedDict, total=False):
    organizationId: str
    key: str
    size: float
    mime: str
    md5: str
    preview: str
    created: str
    modified: str


class ObjectJobResult(TypedDict, total=False):
    organizationId: str
    jobId: str
    keys: List[str]
    url: str


class ObjectStoreEntry(TypedDict, total=False):
    key: str
    name: str
    folder: bool
    size: float
    mime: str
    modified: str


class ObjectStoreListData(TypedDict, total=False):
    organizationId: str
    path: str
    entries: List[ObjectStoreEntry]
    page: int
    totalPages: int
    objectStorageUsed: int
    objectStorageUsedHuman: str


def _decode_object_data(data: str, base64_encoded: bool) -> bytes | None:
    if base64_encoded:
        try:
            return b64decode(data)
        except Exception:
            return None
    return data.encode("utf-8")


def _extract_metadata(organization_id: str, payload: Dict[str, Any]) -> ObjectMetadata:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return ObjectMetadata(
        organizationId=organization_id,
        key=str(metadata.get("key") or ""),
        size=float(metadata.get("size") or 0.0),
        mime=str(metadata.get("mime") or ""),
        md5=str(metadata.get("md5") or ""),
        preview=str(metadata.get("preview") or ""),
        created=str(metadata.get("created") or ""),
        modified=str(metadata.get("modified") or ""),
    )


def _extract_list(organization_id: str, payload: Dict[str, Any]) -> ObjectStoreListData:
    entries: List[ObjectStoreEntry] = []
    objects = payload.get("objects")
    if isinstance(objects, list):
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            entries.append(
                ObjectStoreEntry(
                    key=str(obj.get("key") or ""),
                    name=str(obj.get("name") or ""),
                    folder=bool(obj.get("folder") or False),
                    size=float(obj.get("size") or 0.0),
                    mime=str(obj.get("mime") or ""),
                    modified=str(obj.get("modified") or ""),
                )
            )
    data: ObjectStoreListData = ObjectStoreListData(
        organizationId=organization_id,
        path=str(payload.get("path") or ""),
        entries=entries,
    )
    if "page" in payload:
        try:
            data["page"] = int(payload.get("page") or 0)
        except (TypeError, ValueError):
            data["page"] = 0
    if "totalPages" in payload:
        try:
            data["totalPages"] = int(payload.get("totalPages") or 0)
        except (TypeError, ValueError):
            data["totalPages"] = 0
    if "objectStorageUsed" in payload:
        try:
            data["objectStorageUsed"] = int(payload.get("objectStorageUsed") or 0)
        except (TypeError, ValueError):
            data["objectStorageUsed"] = 0
    if "objectStorageUsedHuman" in payload:
        data["objectStorageUsedHuman"] = str(payload.get("objectStorageUsedHuman") or "")
    return data


def register_object_store_tools(mcp):
    @mcp.tool(annotations={"title": "Upload Object Store file", "idempotentHint": True})
    async def upload_object(
        organizationId: str,
        key: str,
        objectData: str,
        base64Encoded: bool,
    ) -> ToolResult:
        if not organizationId.strip():
            return error_result(
                "validation-error",
                "organizationId is required",
                "Provide the QuantConnect organization id.",
            )
        if not key.strip():
            return error_result("validation-error", "key is required", "Provide the object store key.")

        data_bytes = _decode_object_data(objectData, base64Encoded)
        if data_bytes is None:
            return error_result(
                "validation-error",
                "objectData must be valid base64 when base64Encoded is true",
                "Set base64Encoded to false when sending plain text.",
            )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/object/set",
                    headers=get_headers(),
                    data={"organizationId": organizationId, "key": key},
                    files={"objectData": data_bytes},
                    timeout=30.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return error_result(
                    "api-http-error",
                    f"HTTP {exc.response.status_code}: {exc.response.text}",
                    "Verify organization id, key, and credentials.",
                )
            except httpx.RequestError as exc:
                return error_result("api-request-error", str(exc), "Check MCP network connectivity.")

        payload: Dict[str, Any]
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        result: ObjectUploadResult = ObjectUploadResult(
            organizationId=organizationId,
            key=key,
            bytes=len(data_bytes),
            raw=payload,
        )
        return success_result(result)  # type: ignore[arg-type]

    register_tool_contract(
        "upload_object",
        upload_object,
        mcp,
        defaults={"base64Encoded": False},
    )

    @mcp.tool(
        annotations={"title": "Read Object Store file properties", "readOnlyHint": True}
    )
    async def read_object_properties(organizationId: str, key: str) -> ToolResult:
        if not organizationId.strip() or not key.strip():
            return error_result(
                "validation-error",
                "organizationId and key are required",
                "Provide the organization id and object store key.",
            )

        payload = {"organizationId": organizationId, "key": key}
        return await execute_api_call(
            "/object/properties",
            payload,
            transform=lambda data: _extract_metadata(organizationId, data),
        )

    register_tool_contract("read_object_properties", read_object_properties, mcp)

    @mcp.tool(
        annotations={"title": "Read Object Store file job Id", "destructiveHint": False}
    )
    async def read_object_store_file_job_id(organizationId: str, keys: List[str]) -> ToolResult:
        if not organizationId.strip():
            return error_result(
                "validation-error",
                "organizationId is required",
                "Provide the QuantConnect organization id.",
            )
        if not keys:
            return error_result(
                "validation-error",
                "keys must include at least one entry",
                "Provide one or more object store keys to download.",
            )

        payload = {"organizationId": organizationId, "keys": keys}

        def transform(data: Dict[str, Any]) -> ObjectJobResult:
            return ObjectJobResult(
                organizationId=organizationId,
                jobId=str(data.get("jobId") or ""),
                keys=keys,
            )

        return await execute_api_call("/object/get", payload, transform=transform)

    register_tool_contract("read_object_store_file_job_id", read_object_store_file_job_id, mcp)

    @mcp.tool(
        annotations={"title": "Read Object Store file download URL", "readOnlyHint": True}
    )
    async def read_object_store_file_download_url(organizationId: str, jobId: str) -> ToolResult:
        if not organizationId.strip() or not jobId.strip():
            return error_result(
                "validation-error",
                "organizationId and jobId are required",
                "Provide both organization id and job id.",
            )

        payload = {"organizationId": organizationId, "jobId": jobId}

        def transform(data: Dict[str, Any]) -> ObjectJobResult:
            return ObjectJobResult(
                organizationId=organizationId,
                jobId=jobId,
                url=str(data.get("url") or ""),
            )

        return await execute_api_call("/object/get", payload, transform=transform)

    register_tool_contract("read_object_store_file_download_url", read_object_store_file_download_url, mcp)

    @mcp.tool(annotations={"title": "List Object Store files", "readOnlyHint": True})
    async def list_object_store_files(organizationId: str, path: str) -> ToolResult:
        if not organizationId.strip():
            return error_result(
                "validation-error",
                "organizationId is required",
                "Provide the QuantConnect organization id.",
            )

        payload: Dict[str, Any] = {"organizationId": organizationId}
        if path:
            payload["path"] = path

        return await execute_api_call(
            "/object/list",
            payload,
            transform=lambda data: _extract_list(organizationId, data),
        )

    register_tool_contract(
        "list_object_store_files",
        list_object_store_files,
        mcp,
        defaults={"path": ""},
        safe=False,
    )

    @mcp.tool(annotations={"title": "Delete Object Store file", "idempotentHint": True})
    async def delete_object(organizationId: str, key: str) -> ToolResult:
        if not organizationId.strip() or not key.strip():
            return error_result(
                "validation-error",
                "organizationId and key are required",
                "Provide the organization id and object store key.",
            )

        payload = {"organizationId": organizationId, "key": key}

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"organizationId": organizationId, "key": key, "deleted": True}

        return await execute_api_call("/object/delete", payload, transform=transform)

    register_tool_contract("delete_object", delete_object, mcp)
