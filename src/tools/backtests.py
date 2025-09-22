from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class BacktestData(TypedDict, total=False):
    projectId: int
    backtestId: str
    name: str
    status: str
    note: str
    progress: float
    parameters: Dict[str, Any]
    equity: float
    raw: Dict[str, Any]


class BacktestListData(TypedDict, total=False):
    projectId: int
    count: int
    backtests: List[BacktestData]


class BacktestChartData(TypedDict, total=False):
    projectId: int
    backtestId: str
    chartName: str
    seriesCount: int
    raw: Dict[str, Any]


class BacktestOrdersData(TypedDict, total=False):
    projectId: int
    backtestId: str
    orderCount: int
    raw: Dict[str, Any]


class BacktestInsightsData(TypedDict, total=False):
    projectId: int
    backtestId: str
    insightCount: int
    raw: Dict[str, Any]


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


def _normalize_parameters(data: Any) -> Dict[str, Any]:
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items()}
    return {}


def _extract_backtest(project_id: int, payload: Dict[str, Any]) -> BacktestData:
    backtest_id = str(payload.get("backtestId") or payload.get("id") or "")
    info = BacktestData(
        projectId=project_id,
        backtestId=backtest_id,
        name=str(payload.get("name") or ""),
        status=str(payload.get("status") or payload.get("state") or ""),
        note=str(payload.get("note") or ""),
        progress=_parse_float(payload.get("progress")) or 0.0,
        parameters=_normalize_parameters(payload.get("parameterSet") or payload.get("parameters")),
        equity=_parse_float(payload.get("equity")) or 0.0,
        raw=payload,
    )
    return info


def register_backtest_tools(mcp):
    @mcp.tool(
        annotations={"title": "Create backtest", "destructiveHint": False}
    )
    async def create_backtest(
        projectId: str,
        compileId: str,
        backtestName: str,
        parameters: Dict[str, Any],
        note: str,
    ) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        if not compileId.strip():
            return error_result("validation-error", "compileId is required", "Provide the compile id to backtest.")
        payload: Dict[str, Any] = {
            "projectId": project_id,
            "compileId": compileId,
            "backtestName": backtestName,
        }
        if parameters:
            payload["parameters"] = parameters
        if note:
            payload["note"] = note

        def transform(data: Dict[str, Any]) -> BacktestData:
            backtest = data.get("backtest")
            if isinstance(backtest, dict):
                return _extract_backtest(project_id, backtest)
            return BacktestData(projectId=project_id, backtestId="", name="", status="", raw=data)

        return await execute_api_call("/backtests/create", payload, transform=transform)

    register_tool_contract(
        "create_backtest",
        create_backtest,
        mcp,
        defaults={"parameters": {}, "note": ""},
    )

    @mcp.tool(annotations={"title": "Read backtest", "readOnlyHint": True})
    async def read_backtest(projectId: str, backtestId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip():
            return error_result(
                "validation-error",
                "projectId and backtestId are required",
                "Provide the project id and backtest id.",
            )

        payload = {"projectId": project_id, "backtestId": backtestId}

        def transform(data: Dict[str, Any]) -> BacktestData:
            backtest = data.get("backtest")
            if isinstance(backtest, dict):
                return _extract_backtest(project_id, backtest)
            return BacktestData(projectId=project_id, backtestId=backtestId, name="", status="", raw=data)

        return await execute_api_call("/backtests/read", payload, transform=transform)

    register_tool_contract("read_backtest", read_backtest, mcp)

    @mcp.tool(annotations={"title": "List backtests", "readOnlyHint": True})
    async def list_backtests(projectId: str, start: str, end: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        payload: Dict[str, Any] = {"projectId": project_id}
        if start:
            start_int = _parse_int(start)
            if start_int is None:
                return error_result("validation-error", "start must be numeric", "Provide a numeric start index.")
            payload["start"] = start_int
        if end:
            end_int = _parse_int(end)
            if end_int is None:
                return error_result("validation-error", "end must be numeric", "Provide a numeric end index.")
            payload["end"] = end_int

        def transform(data: Dict[str, Any]) -> BacktestListData:
            backtests = []
            items = data.get("backtests")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        pid = _parse_int(item.get("projectId")) or project_id
                        backtests.append(_extract_backtest(pid, item))
            return BacktestListData(projectId=project_id, count=len(backtests), backtests=backtests)

        return await execute_api_call("/backtests/list", payload, transform=transform)

    register_tool_contract(
        "list_backtests",
        list_backtests,
        mcp,
        defaults={"start": "", "end": ""},
        safe=False,
    )

    @mcp.tool(annotations={"title": "Read backtest chart", "readOnlyHint": True})
    async def read_backtest_chart(projectId: str, backtestId: str, chartName: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip() or not chartName.strip():
            return error_result(
                "validation-error",
                "projectId, backtestId, and chartName are required",
                "Provide the project id, backtest id, and chart name.",
            )

        payload = {"projectId": project_id, "backtestId": backtestId, "chartName": chartName}

        def transform(data: Dict[str, Any]) -> BacktestChartData:
            chart = data.get("chart")
            series_count = 0
            if isinstance(chart, dict):
                series = chart.get("series")
                if isinstance(series, dict):
                    series_count = len(series)
            return BacktestChartData(
                projectId=project_id,
                backtestId=backtestId,
                chartName=chartName,
                seriesCount=series_count,
                raw=data,
            )

        return await execute_api_call("/backtests/chart/read", payload, transform=transform)

    register_tool_contract("read_backtest_chart", read_backtest_chart, mcp)

    @mcp.tool(annotations={"title": "Read backtest orders", "readOnlyHint": True})
    async def read_backtest_orders(projectId: str, backtestId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip():
            return error_result(
                "validation-error",
                "projectId and backtestId are required",
                "Provide the project id and backtest id.",
            )

        payload = {"projectId": project_id, "backtestId": backtestId}

        def transform(data: Dict[str, Any]) -> BacktestOrdersData:
            orders = data.get("orders")
            count = len(orders) if isinstance(orders, list) else 0
            return BacktestOrdersData(projectId=project_id, backtestId=backtestId, orderCount=count, raw=data)

        return await execute_api_call("/backtests/orders/read", payload, transform=transform)

    register_tool_contract("read_backtest_orders", read_backtest_orders, mcp)

    @mcp.tool(annotations={"title": "Read backtest insights", "readOnlyHint": True})
    async def read_backtest_insights(projectId: str, backtestId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip():
            return error_result(
                "validation-error",
                "projectId and backtestId are required",
                "Provide the project id and backtest id.",
            )

        payload = {"projectId": project_id, "backtestId": backtestId}

        def transform(data: Dict[str, Any]) -> BacktestInsightsData:
            insights = data.get("insights")
            count = len(insights) if isinstance(insights, list) else 0
            return BacktestInsightsData(projectId=project_id, backtestId=backtestId, insightCount=count, raw=data)

        return await execute_api_call("/backtests/read/insights", payload, transform=transform)

    register_tool_contract("read_backtest_insights", read_backtest_insights, mcp)

    @mcp.tool(annotations={"title": "Update backtest", "idempotentHint": True})
    async def update_backtest(
        projectId: str,
        backtestId: str,
        name: str,
        note: str,
    ) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip():
            return error_result(
                "validation-error",
                "projectId and backtestId are required",
                "Provide the project id and backtest id.",
            )
        if not name.strip() and not note.strip():
            return error_result(
                "validation-error",
                "Provide a name and/or note",
                "Specify at least one field to update.",
            )

        payload: Dict[str, Any] = {"projectId": project_id, "backtestId": backtestId}
        if name:
            payload["name"] = name
        if note:
            payload["note"] = note

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"projectId": project_id, "backtestId": backtestId, "updated": True}

        return await execute_api_call("/backtests/update", payload, transform=transform)

    register_tool_contract(
        "update_backtest",
        update_backtest,
        mcp,
        defaults={"name": "", "note": ""},
    )

    @mcp.tool(annotations={"title": "Delete backtest", "idempotentHint": True})
    async def delete_backtest(projectId: str, backtestId: str) -> ToolResult:
        project_id = _parse_int(projectId)
        if project_id is None or not backtestId.strip():
            return error_result(
                "validation-error",
                "projectId and backtestId are required",
                "Provide the project id and backtest id.",
            )

        payload = {"projectId": project_id, "backtestId": backtestId}

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"projectId": project_id, "backtestId": backtestId, "deleted": True}

        return await execute_api_call("/backtests/delete", payload, transform=transform)

    register_tool_contract("delete_backtest", delete_backtest, mcp)
