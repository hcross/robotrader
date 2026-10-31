"""Contract tests for control plane CORS compliance and optional Bearer auth.

Covers:
- CORS Fetch-specification compliance: allow_credentials=False with wildcard,
  allow_credentials=True with explicit non-wildcard origins.
- Optional Bearer token authentication on mutating POST routes under /api/v1/
  via constant-time comparison (hmac.compare_digest).
- Unauthenticated read-only GET /api/v1/health and GET /api/v1/status.
- Open access when ROBOTRADER_API_TOKEN is unset or empty.

Subprocess isolation is used for full endpoint tests so backend.server is never
imported in the top-level test runner process, keeping test_health.py isolated.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.core.security import resolve_cors_config, verify_bearer_token

CHILD_CORS_SCRIPT = """
from unittest import mock
from backend.agents.orchestrator import OrchestratorAgent
from backend.core import state_store as state_store_module

OrchestratorAgent.start_cognitive_scheduler = lambda self: None
state_store_module.HybridStateStore.start_live_worker = lambda self, interval_sec=10.0: None

import backend.server as server
from fastapi.testclient import TestClient

client = TestClient(server.app)

# 1. Simple request check
res = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
cors_origins, allow_cred = server.cors_origins, server.cors_allow_credentials

# 2. Preflight request check
options_res = client.options(
    "/api/v1/risk/kill",
    headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    },
)

cred_header = options_res.headers.get("access-control-allow-credentials", "false").lower()
print(f"ALLOW_CREDENTIALS_CONFIG={allow_cred}")
print(f"CORS_ORIGINS={cors_origins}")
print(f"OPTIONS_ALLOW_CREDENTIALS={cred_header}")
print("cors child ok")
"""

CHILD_AUTH_SCRIPT = """
from unittest import mock
from backend.agents.orchestrator import OrchestratorAgent
from backend.core import state_store as state_store_module

OrchestratorAgent.start_cognitive_scheduler = lambda self: None
state_store_module.HybridStateStore.start_live_worker = lambda self, interval_sec=10.0: None

import backend.server as server
from fastapi.testclient import TestClient

client = TestClient(server.app)
store = server.state_store

# Ensure clean initial state
store.kill_switch_active = False

# 1. GET /api/v1/health remains unauthenticated
res = client.get("/api/v1/health")
assert res.status_code == 200, f"health failed: {res.status_code}"
assert res.json()["status"] == "ok"

# 2. GET /api/v1/status remains unauthenticated
res = client.get("/api/v1/status")
assert res.status_code == 200, f"status failed: {res.status_code}"

# 3. POST /api/v1/risk/kill without auth is rejected with 401
res = client.post("/api/v1/risk/kill", json={"active": True})
assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
assert res.json() == {"detail": "Invalid or missing API token"}
assert store.kill_switch_active is False, "state must not mutate on auth failure"

# 4. POST /api/v1/treasury/deposit with wrong token is rejected with 401
res = client.post(
    "/api/v1/treasury/deposit",
    json={"amount_usd": 500.0},
    headers={"Authorization": "Bearer wrong-token"},
)
assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
assert res.json() == {"detail": "Invalid or missing API token"}

# 5. POST /api/v1/risk/kill with malformed scheme (Basic) is rejected with 401
res = client.post(
    "/api/v1/risk/kill",
    json={"active": True},
    headers={"Authorization": "Basic secret-token-123"},
)
assert res.status_code == 401, f"expected 401, got {res.status_code}: {res.text}"
assert res.json() == {"detail": "Invalid or missing API token"}
assert store.kill_switch_active is False, "state must not mutate on auth failure"

# 6. POST /api/v1/risk/kill with valid Bearer token is accepted
res = client.post(
    "/api/v1/risk/kill",
    json={"active": True, "reason": "Authorized test"},
    headers={"Authorization": "Bearer secret-token-123"},
)
assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"
assert store.kill_switch_active is True, "kill switch should be active after authorized request"

print("auth child ok")
"""

CHILD_UNSET_AUTH_SCRIPT = """
from unittest import mock
from backend.agents.orchestrator import OrchestratorAgent
from backend.core import state_store as state_store_module

OrchestratorAgent.start_cognitive_scheduler = lambda self: None
state_store_module.HybridStateStore.start_live_worker = lambda self, interval_sec=10.0: None

import backend.server as server
from fastapi.testclient import TestClient

client = TestClient(server.app)
store = server.state_store
store.kill_switch_active = False

# POST without Authorization header succeeds when ROBOTRADER_API_TOKEN is unset
res = client.post("/api/v1/risk/kill", json={"active": True, "reason": "Unset dev mode"})
assert res.status_code == 200, f"expected 200, got {res.status_code}: {res.text}"
assert store.kill_switch_active is True

print("unset auth child ok")
"""


class TestCorsConfigUnit(unittest.TestCase):
    def test_default_unset_disables_credentials(self) -> None:
        origins, allow_cred = resolve_cors_config(None)
        self.assertEqual(origins, ["*"])
        self.assertFalse(allow_cred)

    def test_empty_or_whitespace_disables_credentials(self) -> None:
        for empty_val in ("", "   ", "\t\n"):
            with self.subTest(empty_val=empty_val):
                origins, allow_cred = resolve_cors_config(empty_val)
                self.assertEqual(origins, ["*"])
                self.assertFalse(allow_cred)

    def test_explicit_origins_enable_credentials(self) -> None:
        origins, allow_cred = resolve_cors_config("http://localhost:5173,http://127.0.0.1:5173")
        self.assertEqual(origins, ["http://localhost:5173", "http://127.0.0.1:5173"])
        self.assertTrue(allow_cred)

    def test_wildcard_with_explicit_disables_credentials(self) -> None:
        origins, allow_cred = resolve_cors_config("http://localhost:5173,*")
        self.assertIn("*", origins)
        self.assertFalse(allow_cred)


class TestBearerTokenUnit(unittest.TestCase):
    def test_unset_token_allows_anything(self) -> None:
        self.assertTrue(verify_bearer_token(None, ""))
        self.assertTrue(verify_bearer_token("Bearer foo", ""))

    def test_matching_token_accepted(self) -> None:
        self.assertTrue(verify_bearer_token("Bearer secret-123", "secret-123"))

    def test_mismatched_token_rejected(self) -> None:
        self.assertFalse(verify_bearer_token("Bearer wrong", "secret-123"))

    def test_missing_or_empty_header_rejected(self) -> None:
        self.assertFalse(verify_bearer_token(None, "secret-123"))
        self.assertFalse(verify_bearer_token("", "secret-123"))

    def test_malformed_scheme_rejected(self) -> None:
        self.assertFalse(verify_bearer_token("Basic secret-123", "secret-123"))
        self.assertFalse(verify_bearer_token("Bearer", "secret-123"))
        self.assertFalse(verify_bearer_token("bearer secret-123", "secret-123"))
        self.assertFalse(verify_bearer_token("Token secret-123", "secret-123"))


class TestControlPlaneSecurityIntegration(unittest.TestCase):
    def _run_child(self, script: str, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "COSTGUARD_LEDGER_PATH": str(Path(tmp) / "ledger.jsonl"),
                **env_overrides,
            }
            return subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )

    def test_cors_default_wildcard_disables_credentials(self) -> None:
        res = self._run_child(CHILD_CORS_SCRIPT, {"CORS_ALLOWED_ORIGINS": ""})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ALLOW_CREDENTIALS_CONFIG=False", res.stdout)
        self.assertIn("cors child ok", res.stdout)

    def test_cors_explicit_origins_enables_credentials(self) -> None:
        res = self._run_child(
            CHILD_CORS_SCRIPT,
            {"CORS_ALLOWED_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173"},
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ALLOW_CREDENTIALS_CONFIG=True", res.stdout)
        self.assertIn("OPTIONS_ALLOW_CREDENTIALS=true", res.stdout)
        self.assertIn("cors child ok", res.stdout)

    def test_cors_explicit_wildcard_disables_credentials(self) -> None:
        res = self._run_child(
            CHILD_CORS_SCRIPT,
            {"CORS_ALLOWED_ORIGINS": "http://localhost:5173,*"},
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("ALLOW_CREDENTIALS_CONFIG=False", res.stdout)
        self.assertIn("cors child ok", res.stdout)

    def test_bearer_token_enforcement(self) -> None:
        res = self._run_child(CHILD_AUTH_SCRIPT, {"ROBOTRADER_API_TOKEN": "secret-token-123"})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("auth child ok", res.stdout)

    def test_unset_token_allows_unauthenticated_requests(self) -> None:
        res = self._run_child(CHILD_UNSET_AUTH_SCRIPT, {"ROBOTRADER_API_TOKEN": ""})
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("unset auth child ok", res.stdout)

    def test_module_does_not_leak_server_import(self) -> None:
        self.assertNotIn("backend.server", sys.modules)


if __name__ == "__main__":
    unittest.main()
