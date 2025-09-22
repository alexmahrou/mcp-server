from __future__ import annotations

import webbrowser
from typing import Any, Dict, List, TypedDict

import httpx
from pydantic_core import to_jsonable_python

from api_connection import BASE_URL, get_headers
from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class AuthorizationData(TypedDict, total=False):
    redirectUrl: str
    tokenKeys: List[str]
    authorization: Dict[str, Any]
    raw: Dict[str, Any]


class LiveDeploymentData(TypedDict, total=False):
    projectId: int
    deployId: str
    nodeId: str
    status: str
    brokerage: str
    versionId: int
    name: str
    launched: str
    raw: Dict[str, Any]


class LiveListData(TypedDict, total=False):
    projectId: int
    statusFilter: str
    count: int
    deployments: List[LiveDeploymentData]


class LivePortfolioData(TypedDict, total=False):
    projectId: int
    holdings: int
    cash: float
    raw: Dict[str, Any]


class LiveOrdersData(TypedDict, total=False):
    projectId: int
    backtestId: str
    orderCount: int
    offset: int
    raw: Dict[str, Any]


class LiveLogsData(TypedDict, total=False):
    projectId: int
    deployId: str
    lines: int
    total: int
    raw: Dict[str, Any]


class LiveInsightsData(TypedDict, total=False):
    projectId: int
    count: int
    start: int
    end: int
    raw: Dict[str, Any]


class LiveChartData(TypedDict, total=False):
    projectId: int
    chartName: str
    seriesCount: int
    raw: Dict[str, Any]


class LiveActionData(TypedDict, total=False):
    projectId: int
    action: str
    completed: bool


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stringify(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "status", "state"):
            if key in value and value[key] is not None:
                return str(value[key])
    if value is None:
        return ""
    return str(value)


def _normalize_live_summary(project_id: int, payload: Dict[str, Any]) -> LiveDeploymentData:
    return LiveDeploymentData(
        projectId=project_id,
        deployId=_stringify(payload.get("deployId") or payload.get("id")),
        nodeId=_stringify(payload.get("nodeId") or payload.get("hostingId")),
        status=_stringify(payload.get("status")),
        brokerage=_stringify(payload.get("brokerage")),
        versionId=_parse_int(payload.get("versionId")) or 0,
        name=_stringify(payload.get("name") or payload.get("projectName")),
        launched=_stringify(payload.get("launched") or payload.get("created")),
        raw=payload,
    )


def register_live_trading_tools(mcp):
    @mcp.tool(
        annotations={
            "title": "Authorize external connection",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        }
    )
    async def authorize_connection(brokerage: Dict[str, Any]) -> ToolResult:
        if not isinstance(brokerage, dict) or not brokerage:
            return error_result(
                "validation-error",
                "brokerage configuration must be provided",
                "Provide a dictionary describing the brokerage connection you want to authorize.",
            )

        payload = to_jsonable_python({"brokerage": brokerage}, exclude_none=True)

        async with httpx.AsyncClient(follow_redirects=False) as client:
            try:
                response = await client.post(
                    f"{BASE_URL}/live/auth0/authorize",
                    headers=get_headers(),
                    json=payload,
                    timeout=300.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                return error_result(
                    "api-http-error",
                    f"HTTP {exc.response.status_code}: {exc.response.text}",
                    "Verify brokerage credentials and try again.",
                )
            except httpx.RequestError as exc:
                return error_result("api-request-error", str(exc), "Check MCP network connectivity.")

        redirect_url = response.headers.get("Location", "")
        if redirect_url:
            try:
                webbrowser.open(redirect_url)
            except Exception:
                pass

        read_result = await execute_api_call(
            "/live/auth0/read",
            payload,
            timeout=800.0,
            transform=lambda data: {
                "authorization": data.get("authorization") or {},
                "raw": data,
            },
        )

        if read_result["success"]:
            data = dict(read_result["data"])
            authorization = data.get("authorization", {})
            if not isinstance(authorization, dict):
                authorization = {}
            data.update(
                {
                    "redirectUrl": redirect_url,
                    "tokenKeys": [str(k) for k in authorization.keys()],
                    "authorization": authorization,
                }
            )
            read_result["data"] = data
        return read_result

    register_tool_contract("authorize_connection", authorize_connection, mcp)

    @mcp.tool(
        annotations={"title": "Create live algorithm", "destructiveHint": False}
    )
    async def create_live_algorithm(
        projectId: str,
        compileId: str,
        nodeId: str,
        versionId: str,
        brokerage: Dict[str, Any],
        dataProviders: Dict[str, Any],
        parameters: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        if not compileId.strip():
            return error_result(
                "validation-error",
                "compileId is required",
                "Provide the compile id that produced the binaries for this live deployment.",
            )
        if not nodeId.strip():
            return error_result(
                "validation-error",
                "nodeId is required",
                "Select an available live trading node from the project nodes list.",
            )
        if not isinstance(brokerage, dict) or not brokerage:
            return error_result(
                "validation-error",
                "brokerage configuration must be provided",
                "Provide the brokerage settings dictionary required by QuantConnect.",
            )
        if settings and not isinstance(settings, dict):
            return error_result(
                "validation-error",
                "settings must be a dictionary",
                "Pass additional deployment settings via a dictionary.",
            )

        payload: Dict[str, Any] = {
            "projectId": project_id,
            "compileId": compileId,
            "nodeId": nodeId,
            "versionId": versionId,
            "brokerage": brokerage,
        }
        if dataProviders:
            payload["dataProviders"] = dataProviders
        if parameters:
            payload["parameters"] = parameters
        if settings:
            payload.update(settings)

        result = await execute_api_call(
            "/live/create",
            payload,
            transform=lambda data: {
                "projectId": _parse_int(data.get("projectId")) or project_id,
                "deployId": _stringify(data.get("deployId")),
                "status": _stringify((data.get("live") or {}).get("status")),
                "brokerage": _stringify((data.get("live") or {}).get("brokerage")),
                "nodeId": _stringify((data.get("live") or {}).get("nodeId")),
                "versionId": _parse_int(data.get("versionId")) or 0,
                "raw": data,
            },
        )
        return result

    register_tool_contract(
        "create_live_algorithm",
        create_live_algorithm,
        mcp,
        defaults={"dataProviders": {}, "parameters": {}, "settings": {}},
    )

    @mcp.tool(annotations={"title": "Read live algorithm", "readOnlyHint": True})
    async def read_live_algorithm(projectId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        return await execute_api_call(
            "/live/read",
            {"projectId": project_id},
            transform=lambda data: _normalize_live_summary(project_id, data.get("live", {})),
        )

    register_tool_contract("read_live_algorithm", read_live_algorithm, mcp)

    @mcp.tool(annotations={"title": "List live algorithms", "readOnlyHint": True})
    async def list_live_algorithms(projectId: str, status: str) -> ToolResult:
        payload: Dict[str, Any] = {}
        status_filter = ""
        if projectId:
            project_id = _parse_int(projectId)
            if project_id is None:
                return error_result(
                    "validation-error",
                    "projectId must be numeric",
                    "Provide the project id as a stringified integer.",
                )
            payload["projectId"] = project_id
        else:
            project_id = 0
        if status:
            status_filter = status
            payload["status"] = status

        return await execute_api_call(
            "/live/list",
            payload,
            transform=lambda data: LiveListData(
                projectId=_parse_int(data.get("projectId")) or project_id,
                statusFilter=status_filter,
                deployments=[
                    _normalize_live_summary(
                        _parse_int(item.get("projectId")) or project_id,
                        item,
                    )
                    for item in data.get("live", [])
                    if isinstance(item, dict)
                ],
                count=len(data.get("live", []) or []),
            ),
        )

    register_tool_contract(
        "list_live_algorithms",
        list_live_algorithms,
        mcp,
        defaults={"projectId": "", "status": ""},
        safe=False,
    )

    @mcp.tool(annotations={"title": "Read live chart", "readOnlyHint": True})
    async def read_live_chart(projectId: str, name: str, count: str, start: str, end: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not name.strip():
            return error_result(
                "validation-error",
                "projectId and name are required",
                "Provide the project id and chart name to retrieve.",
            )

        payload: Dict[str, Any] = {"projectId": project_id, "name": name}
        for key, value in ("count", count), ("start", start), ("end", end):
            parsed = _parse_int(value)
            if parsed is None:
                return error_result(
                    "validation-error",
                    f"{key} must be numeric",
                    "Provide numeric unix timestamps and counts.",
                )
            payload[key] = parsed

        result = await execute_api_call(
            "/live/chart/read",
            payload,
            transform=lambda data: LiveChartData(
                projectId=project_id,
                chartName=name,
                seriesCount=len((data.get("chart") or {}).get("series", {}) or {}),
                raw=data,
            ),
        )
        if result["success"]:
            raw = result["data"].get("raw", {})
            if isinstance(raw, dict) and "progress" in raw:
                return error_result(
                    "chart-loading",
                    f"Chart is generating. Progress: {raw.get('progress', 0)}",
                    "Retry after the live chart finishes loading.",
                )
        return result

    register_tool_contract(
        "read_live_chart",
        read_live_chart,
        mcp,
        defaults={"count": "0", "start": "0", "end": "0"},
    )

    @mcp.tool(annotations={"title": "Read live logs", "readOnlyHint": True})
    async def read_live_logs(
        projectId: str,
        algorithmId: str,
        startLine: str,
        endLine: str,
        format: str,
    ) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not algorithmId.strip():
            return error_result(
                "validation-error",
                "projectId and algorithmId are required",
                "Provide the project id and live deployment id.",
            )

        start_line = _parse_int(startLine)
        end_line = _parse_int(endLine)
        if start_line is None or end_line is None:
            return error_result(
                "validation-error",
                "startLine and endLine must be numeric",
                "Provide numeric line offsets.",
            )

        payload: Dict[str, Any] = {
            "projectId": project_id,
            "algorithmId": algorithmId,
            "startLine": start_line,
            "endLine": end_line,
        }
        if format:
            payload["format"] = format

        return await execute_api_call(
            "/live/logs/read",
            payload,
            transform=lambda data: LiveLogsData(
                projectId=project_id,
                deployId=algorithmId,
                lines=len(data.get("logs", []) or []),
                total=_parse_int(data.get("length")) or 0,
                raw=data,
            ),
        )

    register_tool_contract(
        "read_live_logs",
        read_live_logs,
        mcp,
        defaults={"format": ""},
    )

    @mcp.tool(annotations={"title": "Read live portfolio", "readOnlyHint": True})
    async def read_live_portfolio(projectId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        return await execute_api_call(
            "/live/portfolio/read",
            {"projectId": project_id},
            transform=lambda data: LivePortfolioData(
                projectId=project_id,
                holdings=len(((data.get("portfolio") or {}).get("holdings") or {})),
                cash=_parse_float((data.get("portfolio") or {}).get("cashBook", {}).get("TotalValue")) or 0.0,
                raw=data,
            ),
        )

    register_tool_contract("read_live_portfolio", read_live_portfolio, mcp)

    @mcp.tool(annotations={"title": "Read live orders", "readOnlyHint": True})
    async def read_live_orders(projectId: str, start: str, end: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        start_idx = _parse_int(start)
        end_idx = _parse_int(end)
        if start_idx is None or end_idx is None:
            return error_result(
                "validation-error",
                "start and end must be numeric",
                "Provide numeric start and end indices (end-start <= 1000).",
            )

        result = await execute_api_call(
            "/live/orders/read",
            {"projectId": project_id, "start": start_idx, "end": end_idx},
            transform=lambda data: LiveOrdersData(
                projectId=project_id,
                backtestId=_stringify(data.get("backtestId")),
                orderCount=len(data.get("orders", []) or []),
                offset=_parse_int(data.get("offset")) or 0,
                raw=data,
            ),
        )
        if result["success"]:
            raw = result["data"].get("raw", {})
            if isinstance(raw, dict) and "progress" in raw:
                return error_result(
                    "orders-loading",
                    f"Orders are still loading. Progress: {raw.get('progress', 0)}",
                    "Retry after the live orders finish loading.",
                )
        return result

    register_tool_contract(
        "read_live_orders",
        read_live_orders,
        mcp,
        defaults={"start": "0", "end": "100"},
    )

    @mcp.tool(annotations={"title": "Read live insights", "readOnlyHint": True})
    async def read_live_insights(projectId: str, start: str, end: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        start_idx = _parse_int(start) or 0
        end_idx = _parse_int(end)
        if end_idx is None:
            return error_result(
                "validation-error",
                "end must be numeric",
                "Provide numeric start/end indices for the insight window.",
            )

        return await execute_api_call(
            "/live/insights/read",
            {"projectId": project_id, "start": start_idx, "end": end_idx},
            transform=lambda data: LiveInsightsData(
                projectId=project_id,
                start=start_idx,
                end=end_idx,
                count=len(data.get("insights", []) or []),
                raw=data,
            ),
        )

    register_tool_contract(
        "read_live_insights",
        read_live_insights,
        mcp,
        defaults={"start": "0", "end": "100"},
    )

    @mcp.tool(
        annotations={"title": "Stop live algorithm", "idempotentHint": True}
    )
    async def stop_live_algorithm(projectId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        return await execute_api_call(
            "/live/update/stop",
            {"projectId": project_id},
            transform=lambda _: LiveActionData(projectId=project_id, action="stop", completed=True),
        )

    register_tool_contract("stop_live_algorithm", stop_live_algorithm, mcp)

    @mcp.tool(
        annotations={"title": "Liquidate live algorithm", "idempotentHint": True}
    )
    async def liquidate_live_algorithm(projectId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        return await execute_api_call(
            "/live/update/liquidate",
            {"projectId": project_id},
            transform=lambda _: LiveActionData(projectId=project_id, action="liquidate", completed=True),
        )

    register_tool_contract("liquidate_live_algorithm", liquidate_live_algorithm, mcp)
