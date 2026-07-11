import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from instagraph.openai_client import DEFAULT_MODEL, respond


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="risposta")


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()


class RespondTests(unittest.TestCase):
    def test_uses_injected_client_and_request_options(self):
        client = FakeClient()

        self.assertEqual(
            respond(
                "Riassumi il grafo.",
                instructions="Rispondi in italiano.",
                model="test-model",
                client=client,
            ),
            "risposta",
        )
        self.assertEqual(
            client.responses.calls,
            [
                {
                    "model": "test-model",
                    "input": "Riassumi il grafo.",
                    "instructions": "Rispondi in italiano.",
                    "store": False,
                }
            ],
        )

    def test_uses_environment_model_when_not_overridden(self):
        client = FakeClient()

        with patch.dict(os.environ, {"INSTAGRAPH_OPENAI_MODEL": "env-model"}):
            respond("Ciao", client=client)

        self.assertEqual(client.responses.calls[0]["model"], "env-model")
        self.assertEqual(DEFAULT_MODEL, "gpt-5.6-sol")

    def test_rejects_blank_prompt_without_calling_client(self):
        client = FakeClient()

        with self.assertRaisesRegex(ValueError, "non-empty"):
            respond("  ", client=client)

        self.assertEqual(client.responses.calls, [])

    def test_explains_when_optional_sdk_is_missing(self):
        with patch.dict(sys.modules, {"openai": None}):
            with self.assertRaisesRegex(RuntimeError, "optional"):
                respond("Ciao")


if __name__ == "__main__":
    unittest.main()
