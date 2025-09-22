from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult
from tool_helpers import execute_api_call


class LeanVersionEntry(TypedDict, total=False):
    id: int
    name: str
    description: str
    created: str
    leanHash: str
    leanCloudHash: str
    public: bool


class LeanVersionsData(TypedDict, total=False):
    count: int
    versions: List[LeanVersionEntry]


def _normalize_versions(payload: Dict[str, Any]) -> LeanVersionsData:
    versions_data: List[LeanVersionEntry] = []
    versions = payload.get("versions")
    if isinstance(versions, list):
        for item in versions:
            if not isinstance(item, dict):
                continue
            entry = LeanVersionEntry(
                id=int(item.get("id") or 0),
                name=str(item.get("name") or ""),
                description=str(item.get("description") or ""),
                created=str(item.get("created") or ""),
                leanHash=str(item.get("leanHash") or ""),
                leanCloudHash=str(item.get("leanCloudHash") or ""),
                public=bool(item.get("public") or False),
            )
            versions_data.append(entry)
    return LeanVersionsData(count=len(versions_data), versions=versions_data)


def register_lean_version_tools(mcp):
    @mcp.tool(annotations={"title": "Read LEAN versions", "readOnlyHint": True})
    async def read_lean_versions() -> ToolResult:
        return await execute_api_call(
            "/lean/versions/read",
            {},
            transform=_normalize_versions,
        )

    register_tool_contract("read_lean_versions", read_lean_versions, mcp, safe=False)
