from __future__ import annotations

from typing import Dict, List, TypedDict

from tool_contract import register_tool_contract, ToolResult, error_result
from tool_helpers import execute_api_call


class FilePayload(TypedDict):
    name: str
    content: str


class ErrorPayload(TypedDict, total=False):
    message: str
    stacktrace: str


class BacktestInitData(TypedDict, total=False):
    state: str
    payload: str
    payloadType: str
    version: float


class CodeCompletionData(TypedDict):
    suggestions: List[str]
    count: int


class EnhancedErrorData(TypedDict):
    enhancedMessage: str


class Pep8Conversion(TypedDict):
    name: str
    content: str


class Pep8Data(TypedDict):
    files: List[Pep8Conversion]
    count: int


class SyntaxIssueData(TypedDict):
    issues: List[str]
    count: int


class SearchCriteriaInput(TypedDict):
    input: str
    type: str
    count: str


class SearchRetrievalData(TypedDict, total=False):
    url: str
    score: float
    content: str
    type: float


class SearchData(TypedDict):
    results: List[SearchRetrievalData]
    count: int


def _validate_files(files: List[FilePayload]) -> List[FilePayload]:
    normalized: List[FilePayload] = []
    for file in files:
        if not isinstance(file, dict):
            continue
        name = str(file.get("name") or "")
        content = str(file.get("content") or "")
        if name:
            normalized.append(FilePayload(name=name, content=content))
    return normalized


def register_ai_tools(mcp):
    @mcp.tool(
        annotations={
            "title": "Check initialization errors",
            "readOnlyHint": True,
        }
    )
    async def check_initialization_errors(language: str, files: List[FilePayload]) -> ToolResult:
        normalized_files = _validate_files(files)
        if not normalized_files:
            return error_result(
                "validation-error",
                "Provide at least one source file with a name and content.",
                "Include a list of file objects like {'name': 'main.py', 'content': '...'}.",
            )

        payload = {"language": language, "files": normalized_files}

        def transform(data: Dict[str, object]) -> BacktestInitData:
            return BacktestInitData(
                state=str(data.get("state") or ""),
                payload=str(data.get("payload") or ""),
                payloadType=str(data.get("payloadType") or ""),
                version=float(data.get("version") or 0.0),
            )

        return await execute_api_call("/ai/tools/backtest-init", payload, transform=transform)

    register_tool_contract("check_initialization_errors", check_initialization_errors, mcp)

    @mcp.tool(annotations={"title": "Complete code", "readOnlyHint": True})
    async def complete_code(language: str, sentence: str, responseSizeLimit: str) -> ToolResult:
        try:
            size_limit = int(responseSizeLimit)
        except ValueError:
            return error_result(
                "validation-error",
                "responseSizeLimit must be an integer string",
                "Set responseSizeLimit to a numeric string like '10'.",
            )

        payload = {
            "language": language,
            "sentence": sentence,
            "responseSizeLimit": size_limit,
        }

        def transform(data: Dict[str, object]) -> CodeCompletionData:
            suggestions = []
            payload_list = data.get("payload")
            if isinstance(payload_list, list):
                suggestions = [str(item) for item in payload_list]
            return CodeCompletionData(suggestions=suggestions, count=len(suggestions))

        return await execute_api_call("/ai/tools/complete", payload, transform=transform)

    register_tool_contract(
        "complete_code",
        complete_code,
        mcp,
        defaults={"responseSizeLimit": "10"},
    )

    @mcp.tool(
        annotations={"title": "Enhance error message", "readOnlyHint": True}
    )
    async def enhance_error_message(language: str, error: ErrorPayload) -> ToolResult:
        message = str(error.get("message") or "")
        stacktrace = str(error.get("stacktrace") or "")
        if not message:
            return error_result(
                "validation-error",
                "error.message is required",
                "Include the error object with at least a message field.",
            )

        payload = {"language": language, "error": {"message": message}}
        if stacktrace:
            payload["error"]["stacktrace"] = stacktrace

        def transform(data: Dict[str, object]) -> EnhancedErrorData:
            return EnhancedErrorData(enhancedMessage=str(data.get("payload") or ""))

        return await execute_api_call("/ai/tools/error-enhance", payload, transform=transform)

    register_tool_contract("enhance_error_message", enhance_error_message, mcp)

    @mcp.tool(
        annotations={"title": "Update code to PEP8", "readOnlyHint": True}
    )
    async def update_code_to_pep8(files: List[FilePayload]) -> ToolResult:
        normalized_files = _validate_files(files)
        if not normalized_files:
            return error_result(
                "validation-error",
                "Provide at least one source file with a name and content.",
                "Include a list of file objects like {'name': 'file.py', 'content': '...'}.",
            )

        payload = {"files": normalized_files}

        def transform(data: Dict[str, object]) -> Pep8Data:
            results = []
            converted = data.get("payload")
            if isinstance(converted, dict):
                for name, content in converted.items():
                    results.append(Pep8Conversion(name=str(name), content=str(content or "")))
            return Pep8Data(files=results, count=len(results))

        return await execute_api_call("/ai/tools/pep8-convert", payload, transform=transform)

    register_tool_contract("update_code_to_pep8", update_code_to_pep8, mcp)

    @mcp.tool(annotations={"title": "Check syntax", "readOnlyHint": True})
    async def check_syntax(language: str, files: List[FilePayload]) -> ToolResult:
        normalized_files = _validate_files(files)
        if not normalized_files:
            return error_result(
                "validation-error",
                "Provide at least one source file with a name and content.",
                "Include a list of file objects like {'name': 'file.py', 'content': '...'}.",
            )

        payload = {"language": language, "files": normalized_files}

        def transform(data: Dict[str, object]) -> SyntaxIssueData:
            issues = []
            payload_list = data.get("payload")
            if isinstance(payload_list, list):
                issues = [str(item) for item in payload_list]
            return SyntaxIssueData(issues=issues, count=len(issues))

        return await execute_api_call("/ai/tools/syntax-check", payload, transform=transform)

    register_tool_contract("check_syntax", check_syntax, mcp)

    @mcp.tool(annotations={"title": "Search QuantConnect", "readOnlyHint": True})
    async def search_quantconnect(language: str, criteria: List[SearchCriteriaInput]) -> ToolResult:
        normalized_criteria: List[SearchCriteriaInput] = []
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            input_value = str(criterion.get("input") or "")
            if not input_value:
                continue
            type_value = str(criterion.get("type") or "")
            count_value = criterion.get("count", 0)
            try:
                count_int = int(count_value)
            except (TypeError, ValueError):
                count_int = 0
            normalized_criteria.append(
                SearchCriteriaInput(input=input_value, type=type_value, count=count_int)
            )

        if not normalized_criteria:
            return error_result(
                "validation-error",
                "criteria is required",
                "Provide at least one search criterion with input/type/count",
            )

        payload = {"language": language, "criteria": normalized_criteria}

        def transform(data: Dict[str, object]) -> SearchData:
            results = []
            retrivals = data.get("retrivals")
            if isinstance(retrivals, list):
                for item in retrivals:
                    if not isinstance(item, dict):
                        continue
                    score_value = item.get("score")
                    try:
                        score_float = float(score_value) if score_value is not None else 0.0
                    except (TypeError, ValueError):
                        score_float = 0.0
                    type_value = item.get("type")
                    try:
                        type_float = float(type_value) if type_value is not None else 0.0
                    except (TypeError, ValueError):
                        type_float = 0.0
                    results.append(
                        SearchRetrievalData(
                            url=str(item.get("url") or ""),
                            score=score_float,
                            content=str(item.get("content") or ""),
                            type=type_float,
                        )
                    )
            return SearchData(results=results, count=len(results))

        return await execute_api_call("/ai/tools/search", payload, transform=transform)

    register_tool_contract("search_quantconnect", search_quantconnect, mcp)
