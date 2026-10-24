import tempfile
import unittest
from pathlib import Path

from backend.core.agent import CallResult
from backend.core.transcript_palace import (
    TranscriptEntry,
    TranscriptPalace,
    record_llm_call,
)


def _sample_result(ok: bool = True, error: str = "") -> CallResult:
    return CallResult(
        raw_resp='{"thesis_continuity": "CONFIRMED"}' if ok else None,
        model_used="deepseek/deepseek-v4.1-flash",
        prompt_tokens=1200,
        completion_tokens=350 if ok else 0,
        latency_ms=814,
        attempts=[
            {
                "model": "deepseek/deepseek-v4.1-flash",
                "latency_ms": 814 if ok else 22000,
                "ok": ok,
                "prompt_tokens": 1200 if ok else 0,
                "completion_tokens": 350 if ok else 0,
                "error": error,
            }
        ],
        error=error,
    )


def _make_entry(agent: str = "Orchestrator/CognitiveLoop", depth: str = "DEEP_THESIS") -> TranscriptEntry:
    return record_llm_call(
        agent=agent,
        kind="reflection",
        thinking_depth=depth,
        model_requested="deepseek/deepseek-v4.1-flash",
        result=_sample_result(),
        system_prompt="SYS",
        user_prompt="USER",
        parsed_ok=True,
        cost_usd=0.000512,
        tool_calls=[{"name": "fetch_ohlcv:SOL/USDT", "duration_ms": 112, "ok": True, "error": ""}],
        meta={"trigger_source": "TEST"},
    )


class TestTranscriptPalace(unittest.TestCase):
    def test_constructible_without_redis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            palace = TranscriptPalace(redis_cmd_fn=None, redis_url=None, storage_path=Path(tmp) / "t.jsonl")
            self.assertEqual(palace.entries, [])
            self.assertFalse(palace.storage_path.exists())

    def test_add_entry_jsonl_and_recall_recent_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            palace = TranscriptPalace(None, None, path)
            for i in range(3):
                palace.add_entry(_make_entry(agent=f"Agent{i}"))
            recalled = palace.recall_recent(limit=3)
            self.assertEqual(recalled[0]["agent"], "Agent2")  # most recent first
            self.assertEqual(recalled[2]["agent"], "Agent0")
            # JSONL is append-only, oldest first
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            import json

            self.assertEqual(json.loads(lines[-1])["agent"], "Agent2")

    def test_reload_from_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            palace = TranscriptPalace(None, None, path)
            for i in range(5):
                palace.add_entry(_make_entry(agent=f"A{i}"))
            palace2 = TranscriptPalace(None, None, path)  # fresh instance, jsonl replay
            self.assertEqual(len(palace2.entries), 5)
            self.assertEqual(palace2.entries[0].agent, "A4")
            self.assertEqual(palace2.entries[0].prompt_tokens, 1200)

    def test_pagination_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.jsonl"
            palace = TranscriptPalace(None, None, path)
            for i in range(7):
                palace.add_entry(_make_entry(agent="Reflexive" if i % 2 else "ChatAgent", depth="DEEP" if i % 2 else "ECO"))
            page, total = palace.list_entries(offset=2, limit=3)
            self.assertEqual(total, 7)
            self.assertEqual(len(page), 3)
            page_agent, total_agent = palace.list_entries(agent="Reflexive")
            self.assertEqual(total_agent, 3)
            page_depth, total_depth = palace.list_entries(agent="ChatAgent", thinking_depth="ECO")
            self.assertEqual(total_depth, 4)
            page_none, total_none = palace.list_entries(agent="NOSUCH")
            self.assertEqual(total_none, 0)
            self.assertEqual(page_none, [])

    def test_record_llm_call_status_mapping(self) -> None:
        ok_entry = record_llm_call(
            agent="A", kind="reflection", thinking_depth="DEEP", model_requested="m",
            result=_sample_result(True), system_prompt="s", user_prompt="u", parsed_ok=True,
        )
        self.assertEqual(ok_entry.status, "ok")
        self.assertTrue(ok_entry.parsed_ok)
        self.assertEqual(ok_entry.entry_id.startswith("tsc_"), True)

        exhausted = record_llm_call(
            agent="A", kind="reflection", thinking_depth="DEEP", model_requested="m",
            result=_sample_result(False, error="fallback_exhausted"), system_prompt="s", user_prompt="u", parsed_ok=False,
        )
        self.assertEqual(exhausted.status, "fallback_failed")
        self.assertFalse(exhausted.parsed_ok)

        no_key = record_llm_call(
            agent="A", kind="chat", thinking_depth="ECO", model_requested="m",
            result=_sample_result(False, error="no_api_key"), system_prompt="s", user_prompt="u", parsed_ok=False,
        )
        self.assertEqual(no_key.status, "no_api_key")

        budget_locked = record_llm_call(
            agent="A", kind="reflection", thinking_depth="DEEP", model_requested="m",
            result=_sample_result(False), system_prompt="s", user_prompt="u", parsed_ok=False,
            status="llm_skipped_budget",
        )
        self.assertEqual(budget_locked.status, "llm_skipped_budget")

    def test_format_recent_transcripts_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            palace = TranscriptPalace(None, None, Path(tmp) / "t.jsonl")
            self.assertIn("Aucun transcript antérieur", palace.format_recent_transcripts())

            big = TranscriptEntry.from_dict({"raw_completion": "x" * 2000, "parsed_ok": True})
            palace.add_entry(big)
            palace.add_entry(_make_entry())
            out_trunc = palace.format_recent_transcripts(max_completion_chars=1200)
            self.assertIn("tronqué", out_trunc)
            out_short = palace.format_recent_transcripts(max_completion_chars=10, max_total_chars=400)
            self.assertIn("…", out_short)
            self.assertLessEqual(len(out_short), 400)

    def test_memory_cap_200(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            palace = TranscriptPalace(None, None, Path(tmp) / "t.jsonl")
            for i in range(210):
                palace.add_entry(_make_entry(agent=f"A{i}"))
            self.assertEqual(len(palace.entries), 200)
            self.assertEqual(palace.entries[0].agent, "A209")
            self.assertEqual(len(list(Path(tmp).glob("t.jsonl"))), 1)


if __name__ == "__main__":
    unittest.main()