"""Infrastructure for consistent MCP tool contracts and legacy compatibility."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, Iterable
from base64 import b64encode

from typing_extensions import TypedDict

from pydantic import ConfigDict, ValidationError

from mcp.server.fastmcp.tools.tool_manager import ToolManager
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase, FuncMetadata

logger = logging.getLogger(__name__)

# Ensure every generated argument model forbids unknown properties and exposes
# a canonical JSON schema with additionalProperties explicitly disabled.
ArgModelBase.model_config = ConfigDict(
    arbitrary_types_allowed=True,
    extra="forbid",
    json_schema_extra={"additionalProperties": False},
)


@dataclass(slots=True)
class ToolContractConfig:
    """Runtime contract metadata for a registered tool."""

    name: str
    defaults: Dict[str, Any] = field(default_factory=dict)
    safe: bool = False  # Indicates the tool is safe to call in offline smoke tests.


_CONTRACTS: Dict[int, ToolContractConfig] = {}
_CONTRACTS_BY_NAME: Dict[str, ToolContractConfig] = {}
_PATCHED = False


class ToolError(TypedDict):
    code: str
    message: str
    hint: str


class ToolResult(TypedDict):
    success: bool
    error: ToolError
    data: Dict[str, Any]


def initialize_tool_contracts() -> None:
    """Ensure FastMCP hooks are active even before any tool registers metadata."""

    _ensure_patches_applied()


def register_tool_contract(tool_name: str, func: Any, mcp, *, defaults: Dict[str, Any] | None = None, safe: bool = False) -> None:
    """Associate contract metadata with a registered FastMCP tool."""

    tool = mcp._tool_manager.get_tool(tool_name)
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' is not registered and can't be configured")

    config = ToolContractConfig(name=tool.name, defaults=defaults or {}, safe=safe)
    _CONTRACTS[id(tool.fn_metadata)] = config
    _CONTRACTS_BY_NAME[tool.name] = config

    _ensure_patches_applied()


def get_tool_contract(metadata: FuncMetadata | None) -> ToolContractConfig | None:
    if metadata is None:
        return None
    return _CONTRACTS.get(id(metadata))


def list_safe_tools() -> list[str]:
    return [config.name for config in _CONTRACTS_BY_NAME.values() if config.safe]


def get_tool_contract_configs() -> Dict[str, ToolContractConfig]:
    """Return a shallow copy of the registered tool contract metadata."""

    return dict(_CONTRACTS_BY_NAME)


def _ensure_patches_applied() -> None:
    global _PATCHED
    if _PATCHED:
        return

    original_call = FuncMetadata.call_fn_with_arg_validation
    original_tool_call = ToolManager.call_tool

    async def patched_call_fn(
        self: FuncMetadata,
        fn: Any,
        fn_is_async: bool,
        arguments_to_validate: dict[str, Any],
        arguments_to_pass_directly: dict[str, Any] | None,
    ) -> Any:
        config = get_tool_contract(self)
        prepared_arguments: Dict[str, Any]
        raw_arguments = _unwrap_arguments(arguments_to_validate)

        if config and config.defaults:
            prepared_arguments = {**config.defaults, **raw_arguments}
        else:
            prepared_arguments = dict(raw_arguments)

        try:
            arguments_pre_parsed = self.pre_parse_json(prepared_arguments)
            arguments_parsed_model = self.arg_model.model_validate(arguments_pre_parsed)
        except ValidationError as exc:
            if config is None:
                raise
            return _validation_error_response(config, exc)

        arguments_parsed_dict = arguments_parsed_model.model_dump_one_level()
        if arguments_to_pass_directly:
            arguments_parsed_dict |= arguments_to_pass_directly

        if fn_is_async:
            return await fn(**arguments_parsed_dict)
        return fn(**arguments_parsed_dict)

    async def patched_tool_call(
        self: ToolManager,
        name: str,
        arguments: dict[str, Any],
        context: Any = None,
        convert_result: bool = False,
    ) -> Any:
        structured_logging_enabled = os.getenv("MCP_STRUCTURED_LOGS") == "1"
        if structured_logging_enabled:
            logger.info(
                json.dumps(
                    {
                        "stage": "tool-input",
                        "tool": name,
                        "arguments": arguments,
                    },
                    default=str,
                )
            )

        result = await original_tool_call(self, name, arguments, context=context, convert_result=convert_result)

        if structured_logging_enabled:
            logger.info(
                json.dumps(
                    {
                        "stage": "tool-output",
                        "tool": name,
                        "result": result,
                    },
                    default=str,
                )
            )
        return result

    FuncMetadata.call_fn_with_arg_validation = patched_call_fn  # type: ignore[assignment]
    ToolManager.call_tool = patched_tool_call  # type: ignore[assignment]

    _PATCHED = True


def _unwrap_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """Support legacy payloads by unwrapping well-known wrappers."""

    if not isinstance(arguments, dict):
        return {}

    for key in ("args", "model"):
        value = arguments.get(key)
        if isinstance(value, dict):
            return value
    return arguments


def _validation_error_response(config: ToolContractConfig, exc: ValidationError) -> Dict[str, Any]:
    messages = []
    missing = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()) if part != "")
        message = error.get("msg", "Invalid input")
        messages.append(f"{location}: {message}" if location else message)
        if error.get("type") == "missing":
            missing.extend(part for part in error.get("loc", ()) if isinstance(part, str))

    hint = ""
    if missing:
        hint = f"Provide values for required fields: {', '.join(sorted(set(missing)))}"

    return error_result("validation-error", "; ".join(messages) or "Invalid request payload", hint)


def success_result(data: Dict[str, Any]) -> ToolResult:
    """Return a sanitized success payload following the standard envelope."""

    return ToolResult(success=True, error=_empty_error(), data=_sanitize_payload(data))


def error_result(code: str, message: str, hint: str = "") -> ToolResult:
    """Return a standardized error payload."""

    return ToolResult(
        success=False,
        error=ToolError(code=code, message=message, hint=hint),
        data={},
    )


def merge_results(*results: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for result in results:
        merged.update(result)
    return merged


def _empty_error() -> ToolError:
    return ToolError(code="", message="", hint="")


def _sanitize_payload(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, dict):
        return {str(key): _sanitize_payload(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, set):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return b64encode(value).decode("ascii")
    return value
