"""Opt-in, read-only graph chat through the OpenAI Responses API."""

from __future__ import annotations

from importlib import import_module
import json
import os
from typing import Any

from .openai_client import DEFAULT_MODEL


GRAPH_CHAT_INSTRUCTIONS = (
    "Answer graph-specific questions only from the results of the supplied read-only "
    "tools. A community result is a connected component, not an inferred social group. "
    "Do not claim access to accounts, edges, or graph data that the tools did not return."
)


READ_ONLY_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "get_account",
        "description": "Get one account's local graph details.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"username": {"type": "string"}},
            "required": ["username"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_community",
        "description": "Get an account's local connected component.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {"username": {"type": "string"}},
            "required": ["username"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_neighbors",
        "description": "Get an account's local followers or following.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": ["following", "followers", "both"],
                },
            },
            "required": ["username", "direction"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "find_path",
        "description": "Find an undirected social path between two local accounts.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string"},
                "target": {"type": "string"},
            },
            "required": ["start", "target"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "graph_summary",
        "description": "Get aggregate local graph counts.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]


def ask_graph(
    store: Any,
    prompt: str,
    *,
    consent: bool = False,
    model: str | None = None,
    client: Any | None = None,
) -> str:
    """Answer a prompt with explicitly consented, read-only graph tools."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt must be a non-empty string")
    if consent is not True:
        raise PermissionError("explicit consent is required before sending graph data")

    if client is None:
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise RuntimeError("OPENAI_API_KEY must be set to use graph chat")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "OpenAI support is optional; install it with `pip install -e '.[ai]'`."
            ) from exc
        client = OpenAI()

    selected_model = model or os.getenv("INSTAGRAPH_OPENAI_MODEL") or DEFAULT_MODEL
    transcript: list[Any] = [{"role": "user", "content": prompt}]
    response = _create_response(client, selected_model, transcript)

    for _ in range(4):
        output = list(getattr(response, "output", ()) or ())
        calls = [item for item in output if _field(item, "type") == "function_call"]
        if not calls:
            return getattr(response, "output_text", "")

        transcript.extend(output)
        transcript.extend(_function_output(store, call) for call in calls)
        response = _create_response(client, selected_model, transcript)

    if any(
        _field(item, "type") == "function_call"
        for item in getattr(response, "output", ()) or ()
    ):
        raise RuntimeError("graph tool-call limit reached")
    return getattr(response, "output_text", "")


def _create_response(client: Any, model: str, input_value: Any) -> Any:
    return client.responses.create(
        model=model,
        input=list(input_value) if isinstance(input_value, list) else input_value,
        instructions=GRAPH_CHAT_INSTRUCTIONS,
        tools=READ_ONLY_TOOLS,
        store=False,
    )


def _function_output(store: Any, call: Any) -> dict[str, str]:
    call_id = _field(call, "call_id")
    if not isinstance(call_id, str) or not call_id:
        call_id = "missing-call-id"
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": _as_json(_dispatch(store, _field(call, "name"), _field(call, "arguments"))),
    }


def _dispatch(store: Any, name: Any, raw_arguments: Any) -> Any:
    if not isinstance(name, str):
        return {"error": "unknown tool"}
    if not isinstance(raw_arguments, str):
        return {"error": "invalid arguments"}
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {"error": "invalid arguments"}
    if not isinstance(arguments, dict):
        return {"error": "invalid arguments"}

    if name == "get_account":
        if not _strings(arguments, {"username"}):
            return {"error": "invalid arguments"}
        try:
            return import_module(".graph_tools", __package__).get_account(
                store, arguments["username"]
            )
        except (TypeError, ValueError):
            return {"error": "invalid arguments"}
        except Exception:
            return {"error": "graph tool failed"}
    if name == "get_neighbors":
        if not (
            _strings(arguments, {"username", "direction"})
            and arguments["direction"] in {"following", "followers", "both"}
        ):
            return {"error": "invalid arguments"}
        try:
            return import_module(".graph_tools", __package__).get_neighbors(
                store, arguments["username"], arguments["direction"]
            )
        except (TypeError, ValueError):
            return {"error": "invalid arguments"}
        except Exception:
            return {"error": "graph tool failed"}
    if name == "get_community":
        if not _strings(arguments, {"username"}):
            return {"error": "invalid arguments"}
        try:
            return import_module(".graph_tools", __package__).get_community(
                store, arguments["username"]
            )
        except (TypeError, ValueError):
            return {"error": "invalid arguments"}
        except Exception:
            return {"error": "graph tool failed"}
    if name == "find_path":
        if not _strings(arguments, {"start", "target"}):
            return {"error": "invalid arguments"}
        try:
            return import_module(".graph_tools", __package__).find_path(
                store, arguments["start"], arguments["target"]
            )
        except (TypeError, ValueError):
            return {"error": "invalid arguments"}
        except Exception:
            return {"error": "graph tool failed"}
    if name == "graph_summary":
        if arguments:
            return {"error": "invalid arguments"}
        try:
            return import_module(".graph_tools", __package__).graph_summary(store)
        except Exception:
            return {"error": "graph tool failed"}
    return {"error": "unknown tool"}


def _strings(arguments: dict[str, Any], expected: set[str]) -> bool:
    return set(arguments) == expected and all(
        isinstance(value, str) and value.strip() for value in arguments.values()
    )


def _as_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return '{"error":"graph tool returned unsupported data"}'


def _field(item: Any, name: str) -> Any:
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)
