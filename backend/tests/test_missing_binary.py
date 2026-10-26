"""Contracts for the shared Rust binary resolver and the missing-binary 503.

The module never imports ``backend.server`` in-process: the endpoint contract is
exercised in an isolated child process (the ``test_health.py`` pattern), so the
suite never starts the live worker or the cognitive scheduler.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core import state_store as state_store_module
from backend.core.errors import (
    ROBOTRADER_NODE_BUILD_COMMAND,
    RustBinaryNotFoundError,
    rust_binary_not_found_handler,
)
from backend.core.state_store import HybridStateStore, resolve_robotrader_binary

DETAIL_MARKERS = (
    "target/debug/robotrader-node",
    "target/release/robotrader-node",
    ROBOTRADER_NODE_BUILD_COMMAND,
)


def _binary_error() -> RustBinaryNotFoundError:
    return RustBinaryNotFoundError(
        [
            Path("engine-rs/target/debug/robotrader-node"),
            Path("engine-rs/target/release/robotrader-node"),
        ]
    )


def _touch_binary(engine_dir: Path, profile: str) -> Path:
    binary = engine_dir / "target" / profile / "robotrader-node"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text("", encoding="utf-8")
    return binary


class ResolverPrecedenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.engine_dir = Path(self._tmp.name) / "engine-rs"
        self.engine_dir.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_debug_build_is_used_when_present(self) -> None:
        debug = _touch_binary(self.engine_dir, "debug")

        self.assertEqual(resolve_robotrader_binary(self.engine_dir), debug)

    def test_fresh_debug_build_wins_over_release(self) -> None:
        debug = _touch_binary(self.engine_dir, "debug")
        _touch_binary(self.engine_dir, "release")

        self.assertEqual(resolve_robotrader_binary(self.engine_dir), debug)

    def test_release_is_used_as_the_fallback(self) -> None:
        release = _touch_binary(self.engine_dir, "release")

        self.assertEqual(resolve_robotrader_binary(self.engine_dir), release)

    def test_missing_binary_raises_without_spawning_a_compiler(self) -> None:
        with mock.patch.object(state_store_module.subprocess, "run") as run, mock.patch.object(
            state_store_module.subprocess, "Popen"
        ) as popen:
            with self.assertRaises(RustBinaryNotFoundError) as caught:
                resolve_robotrader_binary(self.engine_dir)

        run.assert_not_called()
        popen.assert_not_called()
        detail = str(caught.exception)
        for marker in DETAIL_MARKERS:
            self.assertIn(marker, detail)
        self.assertEqual(caught.exception.detail, detail)

    def test_both_methods_use_the_same_resolved_binary(self) -> None:
        release = _touch_binary(self.engine_dir, "release")
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"net_profit_usd": 0.0, "executions": []}),
            stderr="",
        )
        store = HybridStateStore()

        with mock.patch.object(
            state_store_module, "resolve_robotrader_binary", return_value=release
        ) as resolver, mock.patch.object(
            state_store_module.subprocess, "run", return_value=completed
        ) as run, mock.patch.object(
            state_store_module.subprocess, "Popen"
        ) as popen:
            store.run_rust_backtest()
            store.run_rust_backtest_for_leaf("leaf-not-a-real-leaf")

        self.assertEqual(resolver.call_count, 2)
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.args[0][0], str(release))
        popen.assert_not_called()


class HandlerShapeTest(unittest.TestCase):
    def test_handler_returns_the_uniform_503_json_detail(self) -> None:
        app = FastAPI()
        app.add_exception_handler(RustBinaryNotFoundError, rust_binary_not_found_handler)

        @app.get("/boom")
        def boom() -> None:
            raise _binary_error()

        response = TestClient(app).get("/boom")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["content-type"], "application/json")
        detail = response.json()["detail"]
        self.assertIsInstance(detail, str)
        for marker in DETAIL_MARKERS:
            self.assertIn(marker, detail)


CHILD_SCRIPT = r"""
import sys
from pathlib import Path
from unittest import mock

from backend.core import state_store as state_store_module
from backend.core.errors import RustBinaryNotFoundError
from backend.core.schemas import Message, PolicyEnvelope
from backend.agents.orchestrator import OrchestratorAgent

DETAIL_MARKERS = (
    "target/debug/robotrader-node",
    "target/release/robotrader-node",
    "cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node",
)


def _missing(engine_dir):
    raise RustBinaryNotFoundError(
        [
            engine_dir / "target" / "debug" / "robotrader-node",
            engine_dir / "target" / "release" / "robotrader-node",
        ]
    )


def _no_worker(self, interval_sec=10.0):
    return None


def _no_scheduler(self):
    return None


# The HTTP contract must be isolated from the network-bound background loops.
OrchestratorAgent.start_cognitive_scheduler = _no_scheduler

# Both patches stay active for the whole child process: it exits after its
# assertions, so there is nothing to restore.
mock.patch.object(
    state_store_module, "resolve_robotrader_binary", side_effect=_missing
).start()
mock.patch.object(
    state_store_module.HybridStateStore, "start_live_worker", _no_worker
).start()

import backend.server as server
from fastapi.testclient import TestClient

store = server.state_store
orchestrator = server.orchestrator
client = TestClient(server.app)


def reset():
    store.kill_switch_active = False
    store.kill_switch_reason = None
    baseline = PolicyEnvelope.default_active()
    baseline.envelope_id = "test_baseline"
    store.set_policy(baseline)


def assert_503(response):
    assert response.status_code == 503, (response.status_code, response.text)
    assert response.headers["content-type"].startswith("application/json"), response.headers
    detail = response.json()["detail"]
    for marker in DETAIL_MARKERS:
        assert marker in detail, (marker, detail)


# Read endpoints.
reset()
assert_503(client.get("/api/v1/status"))
reset()
assert_503(client.get("/api/v1/hierarchy"))

# Backtest mutation endpoints.
reset()
assert_503(client.post("/api/v1/backtest/run"))
reset()
assert_503(client.post("/api/v1/leaf/leaf-ethereum/backtest"))

# Policy regime builds the envelope but must not commit it.
reset()
before = store.get_effective_policy().envelope_id
response = client.post("/api/v1/policy/regime", json={"preset": "FULL_SWARM"})
assert_503(response)
assert store.get_effective_policy().envelope_id == before, "regime was committed"
assert not store.get_effective_policy().pod_allocations["pod_sniper"].enabled

# SET_REGIME keeps the eager commit contract.
reset()
orchestrator.meta_allocator.handle_message(
    Message(
        sender="test",
        recipient="MetaAllocator",
        msg_type="SET_REGIME",
        content={"preset": "FULL_SWARM"},
    )
)
committed = store.get_effective_policy()
assert committed.envelope_id.startswith("env_full_swarm_"), committed.envelope_id
assert committed.pod_allocations["pod_sniper"].enabled

# A chat-applied regime stays applied even though the response is a 503.
reset()
assert_503(client.post("/api/v1/chat", json={"command": "full swarm"}))
chat_policy = store.get_effective_policy()
assert chat_policy.envelope_id.startswith("env_full_swarm_"), chat_policy.envelope_id
assert chat_policy.pod_allocations["pod_sniper"].enabled

# Health is independent of the binary.
reset()
health = client.get("/api/v1/health")
assert health.status_code == 200, (health.status_code, health.text)
assert health.headers["content-type"].startswith("application/json")
assert health.json()["status"] == "ok"

# Kill switch runs last: it commits before the resolver raises.
reset()
assert_503(client.post("/api/v1/risk/kill", json={"active": True}))
assert store.kill_switch_active is True

print("missing-binary contract ok")
"""


class MissingBinaryEndpointIntegrationTest(unittest.TestCase):
    def test_endpoints_return_the_uniform_503_in_an_isolated_child(self) -> None:
        # The child imports backend.server, so isolate the CostGuard ledger from
        # any developer ledger at the production default.
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-c", CHILD_SCRIPT],
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    **os.environ,
                    "COSTGUARD_LEDGER_PATH": str(
                        Path(tmp) / "transcript_ledger.jsonl"
                    ),
                },
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing-binary contract ok", result.stdout)
        self.assertNotIn("backend.server", sys.modules)


if __name__ == "__main__":
    unittest.main()
