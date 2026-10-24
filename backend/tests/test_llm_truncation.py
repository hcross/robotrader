"""Truncated-completion recovery on the Warm-Path LLM invocation path.

Production finding (2026-10-20): DEEP_THESIS sent max_tokens=1200, the model
returned exactly 1200 completion tokens with finish_reason="length", the JSON
contract was cut mid-object, parsing failed, and the deterministic fallback
silently took over — the paid completion was discarded.
"""

import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from backend.core.agent import MAX_OUTPUT_TOKENS, BaseWarmAgent
from backend.core.transcript_palace import record_llm_call


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> bool:
        return False


def _opener(sequence, fail_models=()):
    """
    Build a fake `urlopen` replaying `sequence` (one entry per HTTP call) and
    recording the request bodies so the test can assert on `max_tokens`.
    """
    sent = []

    def fake_urlopen(req, timeout=0):  # noqa: ARG001 - urlopen signature
        body = json.loads(req.data.decode("utf-8"))
        sent.append(body)
        if body["model"] in fail_models:
            raise URLError("connection reset")
        spec = sequence[min(len(sent) - 1, len(sequence) - 1)]
        payload = {
            "choices": [
                {
                    "message": {"content": spec.get("content", "")},
                    "finish_reason": spec.get("finish_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": spec.get("prompt_tokens", 100),
                "completion_tokens": spec.get("completion_tokens", 50),
            },
        }
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    return fake_urlopen, sent


class TestTruncationRecovery(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = BaseWarmAgent(name="TestWarm", role="test")
        self.env = patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _invoke(self, opener, max_tokens: int):
        with patch("urllib.request.urlopen", side_effect=opener):
            return self.agent.invoke_openrouter("prompt", max_tokens=max_tokens)

    def test_truncated_completion_escalates_once_and_recovers(self) -> None:
        opener, sent = _opener(
            [
                {"content": '{"thesis_continuity": "REFI', "finish_reason": "length", "completion_tokens": 900},
                {"content": '{"thesis_continuity": "REFINED"}', "finish_reason": "stop", "completion_tokens": 40},
            ]
        )
        result = self._invoke(opener, max_tokens=900)

        self.assertEqual(result.raw_resp, '{"thesis_continuity": "REFINED"}')
        self.assertFalse(result.truncated)
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0]["phase"], "initial")
        self.assertEqual(result.attempts[0]["finish_reason"], "length")
        self.assertEqual(result.attempts[1]["phase"], "escalated")
        self.assertEqual(result.attempts[1]["max_tokens"], 1800)  # escalation floor
        self.assertEqual(sent[0]["max_tokens"], 900)
        self.assertEqual(sent[1]["max_tokens"], 1800)
        # Both attempts were billed: usage must be cumulative, not the last one.
        self.assertEqual(result.prompt_tokens, 200)
        self.assertEqual(result.completion_tokens, 940)

    def test_still_truncated_after_escalation_is_flagged(self) -> None:
        opener, _ = _opener(
            [
                {"content": '{"a":', "finish_reason": "length", "completion_tokens": 900},
                {"content": '{"a": 1, "b":', "finish_reason": "length", "completion_tokens": 1800},
            ]
        )
        result = self._invoke(opener, max_tokens=900)

        self.assertTrue(result.truncated)
        self.assertEqual(result.finish_reason, "length")
        self.assertEqual(len(result.attempts), 2)
        # The longer retry is kept even though it is still incomplete.
        self.assertEqual(result.raw_resp, '{"a": 1, "b":')

        entry = record_llm_call(
            agent="Orchestrator/CognitiveLoop",
            kind="reflection",
            thinking_depth="DEEP_THESIS",
            model_requested="deepseek/deepseek-v4.1-flash",
            result=result,
            system_prompt="SYS",
            user_prompt="USER",
            parsed_ok=False,
        )
        self.assertEqual(entry.status, "truncated_output")
        self.assertTrue(entry.truncated)
        self.assertEqual(entry.finish_reason, "length")

    def test_no_escalation_when_budget_already_at_ceiling(self) -> None:
        opener, sent = _opener([{"content": '{"a":', "finish_reason": "length", "completion_tokens": 900}])
        result = self._invoke(opener, max_tokens=MAX_OUTPUT_TOKENS)

        self.assertEqual(len(sent), 1)
        self.assertTrue(result.truncated)

    def test_failover_still_runs_when_primary_model_is_unreachable(self) -> None:
        opener, sent = _opener(
            [{"content": '{"ok": true}', "finish_reason": "stop", "completion_tokens": 20}],
            fail_models=("deepseek/deepseek-v4.1-flash",),
        )
        result = self._invoke(opener, max_tokens=900)

        self.assertEqual(result.model_used, "z-ai/glm-5.3-flash")
        self.assertEqual(len(sent), 2)
        self.assertFalse(result.attempts[0]["ok"])
        self.assertIn("connection reset", result.attempts[0]["error"])
        self.assertEqual(result.completion_tokens, 20)

    def test_clean_completion_is_not_retried(self) -> None:
        opener, sent = _opener([{"content": '{"ok": true}', "finish_reason": "stop"}])
        result = self._invoke(opener, max_tokens=900)

        self.assertEqual(len(sent), 1)
        self.assertFalse(result.truncated)
        self.assertEqual(result.finish_reason, "stop")


if __name__ == "__main__":
    unittest.main()
