"""Contract tests for the read-only health endpoint.

This module deliberately never imports ``backend.server``: the endpoint must be
exercisable by a probe or a test process without starting background workers,
touching Redis, or reading the state store.
"""

from __future__ import annotations

import builtins
import re
import socket
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.health import health_router, health_snapshot

HEALTH_PATH = "/api/v1/health"
EXPECTED_KEYS = {"status", "service", "timestamp"}
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router)
    return TestClient(app)


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class HealthEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = _build_client()

    def test_healthy_probe_returns_contract(self) -> None:
        response = self.client.get(HEALTH_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        body = response.json()
        self.assertEqual(set(body), EXPECTED_KEYS)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "robotrader")

    def test_payload_excludes_undeclared_data(self) -> None:
        body = self.client.get(HEALTH_PATH).json()

        self.assertEqual(set(body), EXPECTED_KEYS)
        forbidden = {
            "engine_metrics",
            "hierarchy",
            "cost_guard",
            "catalysts",
            "policy_envelope",
        }
        self.assertFalse(forbidden & set(body))

    def test_non_get_method_is_rejected(self) -> None:
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(HEALTH_PATH)
                self.assertEqual(response.status_code, 405)

    def test_repeated_probes_are_idempotent(self) -> None:
        routes_before = [
            (route.path, sorted(getattr(route, "methods", []) or []))
            for route in health_router.routes
        ]

        first = self.client.get(HEALTH_PATH)
        second = self.client.get(HEALTH_PATH)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["status"], second.json()["status"])
        self.assertEqual(first.json()["service"], second.json()["service"])
        self.assertEqual(
            routes_before,
            [
                (route.path, sorted(getattr(route, "methods", []) or []))
                for route in health_router.routes
            ],
        )

    def test_timestamp_is_iso8601_utc(self) -> None:
        timestamp = self.client.get(HEALTH_PATH).json()["timestamp"]

        self.assertRegex(timestamp, TIMESTAMP_RE)
        parsed = _parse_timestamp(timestamp)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset(), timedelta(0))

    def test_timestamp_is_fresh(self) -> None:
        timestamp = self.client.get(HEALTH_PATH).json()["timestamp"]

        clock_after = datetime.now(timezone.utc)
        self.assertLessEqual(abs((clock_after - _parse_timestamp(timestamp)).total_seconds()), 5.0)

    def test_snapshot_uses_injected_utc_clock(self) -> None:
        fixed = datetime(2026, 10, 25, 12, 34, 56, tzinfo=timezone.utc)

        snapshot = health_snapshot(fixed)

        self.assertEqual(set(snapshot), EXPECTED_KEYS)
        self.assertEqual(snapshot["timestamp"], "2026-10-25T12:34:56Z")

    def test_import_and_call_do_not_load_heavy_modules(self) -> None:
        self.assertNotIn("backend.server", sys.modules)

        script = (
            "import sys\n"
            "from fastapi import FastAPI\n"
            "from fastapi.testclient import TestClient\n"
            "from backend.core.health import health_router\n"
            "app = FastAPI()\n"
            "app.include_router(health_router)\n"
            "response = TestClient(app).get('/api/v1/health')\n"
            "assert response.status_code == 200, response.status_code\n"
            "assert 'backend.server' not in sys.modules, 'backend.server was imported'\n"
            "assert 'backend.core.state_store' not in sys.modules, 'state_store was imported'\n"
            "print('isolated')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("isolated", result.stdout)

    def test_dependency_outage_does_not_change_probe(self) -> None:
        real_import = builtins.__import__
        blocked_modules = {"redis", "backend.core.state_store", "backend.server"}

        def guarded_import(name: str, *args: object, **kwargs: object) -> object:
            if name in blocked_modules:
                raise ImportError(f"{name} is unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=guarded_import), mock.patch.object(
            socket, "create_connection", side_effect=OSError("network unavailable")
        ), mock.patch.object(
            socket, "getaddrinfo", side_effect=OSError("network unavailable")
        ):
            response = self.client.get(HEALTH_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
