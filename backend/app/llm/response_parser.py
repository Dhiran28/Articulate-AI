"""
Response parsing (Sprint 4.4): turns a provider's raw text response into
a plain JSON object. This is stage one of two — parse, then validate
(schema_validator.py) — kept as two separate stages because they're two
different failure modes with two different likely causes (see
LLMInvalidResponseError vs. LLMSchemaError in errors.py).

The only "repair" attempted is stripping an optional markdown code fence
(```json ... ``` or ``` ... ```), because that's an extremely common,
mechanical thing well-behaved models do even when asked for raw JSON —
not a guess about the *content* of the response. Anything else that
isn't valid JSON after that one strip is a genuine failure, never
force-parsed or guessed at (ADR 003 §5/§7).
"""

import json
import re
from typing import Any

from .errors import LLMInvalidResponseError

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """
    Returns the parsed JSON object, or raises LLMInvalidResponseError
    (carrying the original `raw_text` for debugging) if the response
    isn't valid JSON, or is valid JSON but not an object (e.g. a bare
    string or array — every schema this layer validates against is a
    JSON object).
    """
    text = raw_text.strip()

    fenced = _CODE_FENCE_PATTERN.match(text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMInvalidResponseError(
            "The provider's response was not valid JSON.",
            raw_response=raw_text,
        ) from exc

    if not isinstance(parsed, dict):
        raise LLMInvalidResponseError(
            "The provider's response was valid JSON but not a JSON object.",
            raw_response=raw_text,
        )

    return parsed
