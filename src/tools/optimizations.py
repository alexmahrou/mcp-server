from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class OptimizationParameterInput(TypedDict, total=False):
    name: str
    min: float
    max: float
    step: float
    minStep: float


class OptimizationConstraintInput(TypedDict, total=False):
    target: str
    operator: str
    value: float


class OptimizationEstimateData(TypedDict, total=False):
    projectId: int
    estimateId: str
    timeSeconds: float
    balance: int


class OptimizationSummary(TypedDict, total=False):
    optimizationId: str
    projectId: int
    name: str
    status: str
    target: str
    compileId: str


class OptimizationListData(TypedDict, total=False):
    projectId: int
    count: int
    optimizations: List[OptimizationSummary]


class OptimizationDetailData(TypedDict, total=False):
    optimizationId: str
    projectId: int
    name: str
    status: str
    target: str
    payload: Dict[str, Any]


def _parse_project_id(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _prepare_parameters(params: List[OptimizationParameterInput]) -> List[Dict[str, Any]] | None:
    normalized: List[Dict[str, Any]] = []
    for param in params:
        if not isinstance(param, dict):
            return None
        name = str(param.get("name") or "")
        min_value = _parse_float(param.get("min"))
        max_value = _parse_float(param.get("max"))
        step_value = _parse_float(param.get("step"))
        if not name or min_value is None or max_value is None or step_value is None:
            return None
        normalized_param: Dict[str, Any] = {
            "name": name,
            "min": min_value,
            "max": max_value,
            "step": step_value,
        }
        if "minStep" in param and param["minStep"] is not None:
            min_step_value = _parse_float(param.get("minStep"))
            if min_step_value is None:
                return None
            normalized_param["minStep"] = min_step_value
        normalized.append(normalized_param)
    return normalized


def _prepare_constraints(constraints: List[OptimizationConstraintInput]) -> List[Dict[str, Any]] | None:
    normalized: List[Dict[str, Any]] = []
    for constraint in constraints:
        if not isinstance(constraint, dict):
            return None
        target = str(constraint.get("target") or "")
        operator = str(constraint.get("operator") or "")
        value = _parse_float(constraint.get("value"))
        if not target or not operator or value is None:
            return None
        normalized.append({"target": target, "operator": operator, "value": value})
    return normalized


def _extract_summary(project_id: int, payload: Dict[str, Any]) -> OptimizationSummary:
    return OptimizationSummary(
        optimizationId=str(payload.get("optimizationId") or payload.get("id") or ""),
        projectId=project_id,
        name=str(payload.get("name") or ""),
        status=str(payload.get("status") or payload.get("state") or ""),
        target=str(payload.get("target") or ""),
        compileId=str(payload.get("compileId") or ""),
    )


def register_optimization_tools(mcp):
    @mcp.tool(
        annotations={"title": "Estimate optimization time", "readOnlyHint": True}
    )
    async def estimate_optimization_time(
        projectId: str,
        name: str,
        target: str,
        targetTo: str,
        strategy: str,
        parameters: List[OptimizationParameterInput],
        compileId: str,
        targetValue: str,
        constraints: List[OptimizationConstraintInput],
    ) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        if not parameters:
            return error_result(
                "validation-error",
                "parameters must include at least one entry",
                "Provide optimization parameters with name/min/max/step.",
            )
        normalized_params = _prepare_parameters(parameters)
        if normalized_params is None:
            return error_result(
                "validation-error",
                "parameters contain invalid values",
                "Ensure each parameter has name, min, max, step as numbers.",
            )
        normalized_constraints = []
        if constraints:
            normalized_constraints = _prepare_constraints(constraints) or []
            if not normalized_constraints and constraints:
                return error_result(
                    "validation-error",
                    "constraints contain invalid values",
                    "Ensure each constraint has target, operator, numeric value.",
                )
        payload: Dict[str, Any] = {
            "projectId": project_id,
            "name": name,
            "target": target,
            "targetTo": targetTo,
            "strategy": strategy,
            "parameters": normalized_params,
        }
        if compileId:
            payload["compileId"] = compileId
        if targetValue:
            target_value_float = _parse_float(targetValue)
            if target_value_float is None:
                return error_result(
                    "validation-error",
                    "targetValue must be numeric",
                    "Provide targetValue as a number or omit it.",
                )
            payload["targetValue"] = target_value_float
        if normalized_constraints:
            payload["constraints"] = normalized_constraints

        def transform(data: Dict[str, Any]) -> OptimizationEstimateData:
            estimate = data.get("estimate")
            estimate_id = ""
            time_seconds = 0.0
            balance = 0
            if isinstance(estimate, dict):
                estimate_id = str(estimate.get("estimateId") or "")
                time_value = _parse_float(estimate.get("time"))
                if time_value is not None:
                    time_seconds = time_value
                balance_value = _parse_int(estimate.get("balance"))
                if balance_value is not None:
                    balance = balance_value
            return OptimizationEstimateData(
                projectId=project_id,
                estimateId=estimate_id,
                timeSeconds=time_seconds,
                balance=balance,
            )

        return await execute_api_call("/optimizations/estimate", payload, transform=transform)

    register_tool_contract(
        "estimate_optimization_time",
        estimate_optimization_time,
        mcp,
        defaults={"compileId": "", "targetValue": "", "constraints": []},
    )

    @mcp.tool(
        annotations={"title": "Create optimization", "destructiveHint": False}
    )
    async def create_optimization(
        projectId: str,
        compileId: str,
        target: str,
        targetTo: str,
        strategy: str,
        parameters: List[OptimizationParameterInput],
        estimatedCost: str,
        nodeType: str,
        parallelNodes: str,
        name: str,
        constraints: List[OptimizationConstraintInput],
        targetValue: str,
    ) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )
        if not compileId.strip():
            return error_result("validation-error", "compileId is required", "Provide the compile id to optimize.")
        normalized_params = _prepare_parameters(parameters)
        if not normalized_params:
            return error_result(
                "validation-error",
                "parameters contain invalid values",
                "Ensure each parameter has name, min, max, step as numbers.",
            )
        normalized_constraints = []
        if constraints:
            normalized_constraints = _prepare_constraints(constraints) or []
            if not normalized_constraints and constraints:
                return error_result(
                    "validation-error",
                    "constraints contain invalid values",
                    "Ensure each constraint has target, operator, numeric value.",
                )
        estimated_cost = _parse_float(estimatedCost)
        if estimated_cost is None:
            return error_result(
                "validation-error",
                "estimatedCost must be numeric",
                "Provide the cost estimate as a number.",
            )
        parallel_nodes = _parse_int(parallelNodes)
        if parallel_nodes is None:
            return error_result(
                "validation-error",
                "parallelNodes must be numeric",
                "Provide the number of parallel nodes as an integer.",
            )

        payload: Dict[str, Any] = {
            "projectId": project_id,
            "compileId": compileId,
            "target": target,
            "targetTo": targetTo,
            "strategy": strategy,
            "parameters": normalized_params,
            "estimatedCost": estimated_cost,
            "nodeType": nodeType,
            "parallelNodes": parallel_nodes,
            "name": name,
        }
        if normalized_constraints:
            payload["constraints"] = normalized_constraints
        if targetValue:
            target_value_float = _parse_float(targetValue)
            if target_value_float is None:
                return error_result(
                    "validation-error",
                    "targetValue must be numeric",
                    "Provide targetValue as a number or omit it.",
                )
            payload["targetValue"] = target_value_float

        def transform(data: Dict[str, Any]) -> OptimizationListData:
            optimizations = []
            items = data.get("optimizations")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        optimizations.append(_extract_summary(project_id, item))
            return OptimizationListData(projectId=project_id, count=len(optimizations), optimizations=optimizations)

        return await execute_api_call("/optimizations/create", payload, transform=transform)

    register_tool_contract(
        "create_optimization",
        create_optimization,
        mcp,
        defaults={"constraints": [], "targetValue": ""},
    )

    @mcp.tool(annotations={"title": "Read optimization", "readOnlyHint": True})
    async def read_optimization(optimizationId: str) -> ToolResult:
        if not optimizationId.strip():
            return error_result(
                "validation-error",
                "optimizationId is required",
                "Provide the optimization id returned by create_optimization.",
            )

        payload = {"optimizationId": optimizationId}

        def transform(data: Dict[str, Any]) -> OptimizationDetailData:
            optimization = data.get("optimization")
            if isinstance(optimization, dict):
                project_id = _parse_int(optimization.get("projectId")) or 0
                summary = _extract_summary(project_id, optimization)
                detail: OptimizationDetailData = OptimizationDetailData(
                    optimizationId=summary.get("optimizationId", ""),
                    projectId=summary.get("projectId", 0),
                    name=summary.get("name", ""),
                    status=summary.get("status", ""),
                    target=summary.get("target", ""),
                    payload=optimization,
                )
                return detail
            return OptimizationDetailData(
                optimizationId=optimizationId,
                projectId=0,
                name="",
                status="",
                target="",
                payload=data,
            )

        return await execute_api_call("/optimizations/read", payload, transform=transform)

    register_tool_contract("read_optimization", read_optimization, mcp)

    @mcp.tool(annotations={"title": "List optimizations", "readOnlyHint": True})
    async def list_optimizations(projectId: str) -> ToolResult:
        project_id = _parse_project_id(projectId)
        if project_id is None:
            return error_result(
                "validation-error",
                "projectId must be numeric",
                "Provide the project id as a stringified integer.",
            )

        payload = {"projectId": project_id}

        def transform(data: Dict[str, Any]) -> OptimizationListData:
            optimizations = []
            items = data.get("optimizations")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        optimizations.append(_extract_summary(project_id, item))
            return OptimizationListData(projectId=project_id, count=len(optimizations), optimizations=optimizations)

        return await execute_api_call("/optimizations/list", payload, transform=transform)

    register_tool_contract("list_optimizations", list_optimizations, mcp, safe=False)

    @mcp.tool(annotations={"title": "Update optimization", "idempotentHint": True})
    async def update_optimization(optimizationId: str, name: str) -> ToolResult:
        if not optimizationId.strip() or not name.strip():
            return error_result(
                "validation-error",
                "optimizationId and name are required",
                "Provide the optimization id and the new name.",
            )

        payload = {"optimizationId": optimizationId, "name": name}

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"optimizationId": optimizationId, "name": name, "updated": True}

        return await execute_api_call("/optimizations/update", payload, transform=transform)

    register_tool_contract("update_optimization", update_optimization, mcp)

    @mcp.tool(annotations={"title": "Abort optimization", "idempotentHint": True})
    async def abort_optimization(optimizationId: str) -> ToolResult:
        if not optimizationId.strip():
            return error_result(
                "validation-error",
                "optimizationId is required",
                "Provide the optimization id returned by create_optimization.",
            )

        payload = {"optimizationId": optimizationId}

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"optimizationId": optimizationId, "aborted": True}

        return await execute_api_call("/optimizations/abort", payload, transform=transform)

    register_tool_contract("abort_optimization", abort_optimization, mcp)

    @mcp.tool(annotations={"title": "Delete optimization", "idempotentHint": True})
    async def delete_optimization(optimizationId: str) -> ToolResult:
        if not optimizationId.strip():
            return error_result(
                "validation-error",
                "optimizationId is required",
                "Provide the optimization id returned by create_optimization.",
            )

        payload = {"optimizationId": optimizationId}

        def transform(_: Dict[str, Any]) -> Dict[str, Any]:
            return {"optimizationId": optimizationId, "deleted": True}

        return await execute_api_call("/optimizations/delete", payload, transform=transform)

    register_tool_contract("delete_optimization", delete_optimization, mcp)
