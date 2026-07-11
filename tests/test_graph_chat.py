import json
import os
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from instagraph.graph_chat import READ_ONLY_TOOLS, ask_graph


class FakeResponses:
    def __init__(self, responses):
        self.calls = []
        self._responses = iter(responses)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)


class FakeClient:
    def __init__(self, responses):
        self.responses = FakeResponses(responses)


def fake_graph_tools():
    module = ModuleType("instagraph.graph_tools")
    module.get_account = lambda store, username: {"username": username}
    module.get_neighbors = lambda store, username, direction: {
        "username": username,
        "direction": direction,
    }
    module.get_community = lambda store, username: {"username": username, "member_count": 2}
    module.find_path = lambda store, start, target: {"path": [start, target]}
    module.graph_summary = lambda store: {"accounts": 2, "edges": 1}
    return module


class GraphChatTests(unittest.TestCase):
    def test_consent_gate_makes_zero_requests(self):
        client = FakeClient([])

        with self.assertRaisesRegex(PermissionError, "consent"):
            ask_graph(object(), "Riassumi", client=client)

        self.assertEqual(client.responses.calls, [])

    def test_rejects_blank_prompt_without_request(self):
        client = FakeClient([])

        with self.assertRaisesRegex(ValueError, "non-empty"):
            ask_graph(object(), "  ", consent=True, client=client)

        self.assertEqual(client.responses.calls, [])

    def test_requires_an_environment_key_only_for_default_client(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                ask_graph(object(), "Riassumi", consent=True)

    def test_uses_strict_read_only_tools_and_handles_a_tool_round(self):
        function_call = SimpleNamespace(
            type="function_call",
            call_id="call-account",
            name="get_account",
            arguments='{"username":"root"}',
        )
        client = FakeClient(
            [
                SimpleNamespace(output=[function_call], output_text=""),
                SimpleNamespace(output=[], output_text="Root is in the graph."),
            ]
        )

        with patch.dict(sys.modules, {"instagraph.graph_tools": fake_graph_tools()}):
            answer = ask_graph(object(), "Trova root", consent=True, client=client)

        self.assertEqual(answer, "Root is in the graph.")
        self.assertEqual(len(client.responses.calls), 2)
        self.assertEqual(
            client.responses.calls[0]["input"],
            [{"role": "user", "content": "Trova root"}],
        )
        for request in client.responses.calls:
            self.assertFalse(request["store"])
            self.assertEqual({tool["name"] for tool in request["tools"]}, {
                "get_account",
                "get_community",
                "get_neighbors",
                "find_path",
                "graph_summary",
            })
        for tool in READ_ONLY_TOOLS:
            self.assertTrue(tool["strict"])
            self.assertFalse(tool["parameters"]["additionalProperties"])

        transcript = client.responses.calls[1]["input"]
        self.assertEqual(transcript[0], {"role": "user", "content": "Trova root"})
        self.assertIs(transcript[1], function_call)
        self.assertEqual(
            transcript[2],
            {
                "type": "function_call_output",
                "call_id": "call-account",
                "output": '{"username":"root"}',
            },
        )

    def test_unknown_and_malformed_calls_return_json_errors(self):
        unknown_call = SimpleNamespace(
            type="function_call",
            call_id="call-unknown",
            name="delete_graph",
            arguments="{}",
        )
        malformed_call = SimpleNamespace(
            type="function_call",
            call_id="call-malformed",
            name="get_account",
            arguments="[]",
        )
        client = FakeClient(
            [
                SimpleNamespace(output=[unknown_call, malformed_call], output_text=""),
                SimpleNamespace(output=[], output_text="Safe answer."),
            ]
        )

        with patch.dict(sys.modules, {"instagraph.graph_tools": fake_graph_tools()}):
            self.assertEqual(
                ask_graph(object(), "Do something", consent=True, client=client),
                "Safe answer.",
            )

        outputs = client.responses.calls[1]["input"][-2:]
        self.assertEqual(json.loads(outputs[0]["output"]), {"error": "unknown tool"})
        self.assertEqual(json.loads(outputs[1]["output"]), {"error": "invalid arguments"})

    def test_stops_after_four_tool_rounds(self):
        responses = [
            SimpleNamespace(
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id=f"call-{index}",
                        name="graph_summary",
                        arguments="{}",
                    )
                ],
                output_text="",
            )
            for index in range(5)
        ]
        client = FakeClient(responses)

        with patch.dict(sys.modules, {"instagraph.graph_tools": fake_graph_tools()}):
            with self.assertRaisesRegex(RuntimeError, "limit"):
                ask_graph(object(), "Continua", consent=True, client=client)

        self.assertEqual(len(client.responses.calls), 5)


if __name__ == "__main__":
    unittest.main()
