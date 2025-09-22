import os

# Load the agent name from the environment variables.
AGENT_NAME = os.getenv('AGENT_NAME', 'MCP Server')


def add_code_source_id(payload):
    """Attach the configured codeSourceId to request payloads."""

    if isinstance(payload, dict):
        payload = dict(payload)
        payload['codeSourceId'] = AGENT_NAME
        return payload

    # Fallback for legacy Pydantic models that expose attribute assignment.
    setattr(payload, 'codeSourceId', AGENT_NAME)
    return payload
