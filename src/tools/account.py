from __future__ import annotations

from typing import Dict, TypedDict

from tool_contract import register_tool_contract, ToolResult
from tool_helpers import execute_api_call


class AccountData(TypedDict, total=False):
    organizationId: str
    accountType: str
    balance: float
    currency: str
    raw: Dict[str, object]


def register_account_tools(mcp):
    @mcp.tool(
        annotations={
            "title": "Read account",
            "readOnlyHint": True,
            "openWorldHint": True,
        }
    )
    async def read_account() -> ToolResult:
        def transform(payload: Dict[str, object]) -> AccountData:
            return AccountData(
                organizationId=str(payload.get("organizationId") or ""),
                accountType=str(payload.get("accountType") or ""),
                currency=str(payload.get("currency") or ""),
                balance=float(payload.get("balance") or 0.0),
                raw=payload,
            )

        return await execute_api_call("/account/read", {}, transform=transform)

    register_tool_contract("read_account", read_account, mcp)
