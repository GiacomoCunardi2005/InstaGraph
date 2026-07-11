"""Small optional bridge to the OpenAI Responses API."""

from __future__ import annotations

import os
from typing import Any


DEFAULT_MODEL = "gpt-5.6-sol"


def respond(
    prompt: str,
    *,
    instructions: str | None = None,
    model: str | None = None,
    client: Any | None = None,
) -> str:
    """Return a text response using an injected or default OpenAI client."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")

    if client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI support is optional; install it with `pip install -e '.[ai]'`."
            ) from exc
        client = OpenAI()

    request: dict[str, Any] = {
        "model": model or os.getenv("INSTAGRAPH_OPENAI_MODEL") or DEFAULT_MODEL,
        "input": prompt,
        "store": False,
    }
    if instructions is not None:
        request["instructions"] = instructions

    return client.responses.create(**request).output_text
