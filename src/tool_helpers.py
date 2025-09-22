"""Shared helpers for MCP tool implementations."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

import httpx

from api_connection import post
from tool_contract import error_result, success_result, ToolResult

logger = logging.getLogger(__name__)

Transform = Callable[[Any], Dict[str, Any]] | None


def _ensure_dict(payload: Any, wrap_key: str) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {wrap_key: payload}
    return {wrap_key: payload}


async def execute_api_call(
    endpoint: str,
    payload: Dict[str, Any] | None = None,
    *,
    timeout: float = 30.0,
    wrap_key: str = "result",
    transform: Callable[[Any], Dict[str, Any]] | None = None,
) -> ToolResult:
    try:
        response = await post(endpoint, payload or {}, timeout)
    except httpx.HTTPStatusError as exc:
        message = _extract_http_error_message(exc)
        hint = "Verify credentials and payload fields for this QuantConnect API call."
        return error_result("api-http-error", message, hint)
    except httpx.RequestError as exc:
        logger.debug("Request error when calling %s: %s", endpoint, exc, exc_info=True)
        return error_result("api-request-error", str(exc), "Check MCP network connectivity.")
    except Exception as exc:  # Unexpected faults should be surfaced but not crash transport.
        logger.exception("Unexpected failure when calling %s", endpoint)
        return error_result("api-internal-error", str(exc), "Retry later or inspect server logs.")

    try:
        if transform is not None:
            data = transform(response)
        else:
            data = _ensure_dict(response, wrap_key)
    except Exception as exc:
        logger.exception("Post-processing failure for tool using %s", endpoint)
        return error_result("result-normalization-error", str(exc), "File a bug with tool inputs.")

    return success_result(data)


def _extract_http_error_message(exc: httpx.HTTPStatusError) -> str:
    response = exc.response
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    detail = ""
    if isinstance(payload, dict):
        for key in ("message", "error", "errors", "details"):
            value = payload.get(key, "")
            if isinstance(value, str) and value:
                detail = value
                break
            if isinstance(value, list) and value:
                detail = "; ".join(str(item) for item in value)
                break
    if not detail:
        detail = response.text or exc.args[0]
    return f"HTTP {response.status_code}: {detail}"
