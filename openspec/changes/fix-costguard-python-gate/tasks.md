# Tasks — fix-costguard-python-gate

> Design: [`design.md`](design.md). Spec: [`specs/costguard/spec.md`](specs/costguard/spec.md) and [`specs/integrity/spec.md`](specs/integrity/spec.md). Reference the spec for *what*; this list only orders *how*. This file replaces the stale Lane S list.

## 1. Injection and the measured source

- [x] 1.1 Add `store: Optional[Any] = None`, `ledger_path: Optional[Path | str] = None`, and `now_ms: Optional[Callable[[], int]] = None` to `LLMMonitorAgent.__init__`; keep the store on the instance, resolve the path per design D10, and store the clock as `self._now_ms` (default `int(time.time() * 1000)`). Do not import `backend.core.state_store`. (covers: "The CostGuard receives its measured PnL source by injection"; design D1, D10, D12)
- [x] 1.2 Add `measured_pnl_source_available`, `_measured_pnl()` (returns `None` without a store, otherwise `float(self.store.measured_realized_pnl_usd())`), and `_kill_switch_active()` (reads only the injected store; `False` when absent). (covers: injection; kill switch; design D1, D2)
- [x] 1.3 Add `ledger_path: Optional[Path | str] = None` to `OrchestratorAgent.__init__` and construct `LLMMonitorAgent(name="CostGuard", store=self.store, ledger_path=ledger_path)`. (covers: "The orchestrator injects its own store instance"; design D1, D17)
- [x] 1.4 Rewrite the automatic branch in `record_usage`: evaluate only when `auto_refill_enabled` and `openrouter_balance_usd <= low_watermark_usd`; resolve `_measured_pnl()`; when it is `None`, return without appending history or changing balance/epoch; otherwise call the gate with that exact value. Add a test where the injected store reports `-$10.00` while a different process-global store reports `$100.00` and no refill occurs. (covers: "The automatic path performs no refill without a measured source"; "The orchestrator injects its own store instance"; negative and zero automatic paths; design D2)
- [x] 1.5 Add `operator_refill(amount_usd=None, force=True, reason=..., source="OPERATOR_REST")`: resolve the injected store's measured helper; `None` returns `rejected_no_pnl_source` with no mutation; otherwise call `trigger_openrouter_refill` with the exact measured value. Add a unit test and an endpoint-level test (existing subprocess pattern) that set the CostGuard store to `None` and assert `rejected_no_pnl_source`. (covers: "The operator path rejects a missing measured source"; "The operator path uses the measured helper"; design D3)
- [x] 1.6 Replace the body of `POST /api/v1/openrouter/refill` with `orchestrator.cost_guard.operator_refill(amount_usd=req.amount_usd, force=req.force)`; remove the direct `state_store.measured_realized_pnl_usd()` argument. (covers: operator injection; design D3)

## 2. Refill gate contract

- [x] 2.1 Make `realized_trading_pnl_usd` a required parameter (no default) of `trigger_openrouter_refill`; verify that a call omitting it raises `TypeError` before any state mutation. (covers: "A call without a realized PnL raises before mutating state"; design D3)
- [x] 2.2 Implement the check order kill switch -> strictly positive PnL -> `(0, $25.00]` bound -> 10 % profit share -> watermark unless `force` -> rolling 24 h epoch cap -> mutation. (covers: "A refill requires strictly positive realized profit"; "Profit-share and epoch caps apply on every path"; design D4, D20)
- [x] 2.3 Return `rejected_kill_switch` first when `_kill_switch_active()`; force, PnL, and caps must not bypass it; leave the balance, epoch total, and history unchanged on both paths. (covers: "Refills are refused while the kill switch is active"; design D4)
- [x] 2.4 Reject zero or negative measured PnL with `rejected_no_realized_profit` and report the verbatim value in `reason`; no `max(...)`, floor, or default may replace it. (covers: "A refill requires strictly positive realized profit"; "No fabricated profit floor"; design D4)
- [x] 2.5 Reject `amount <= 0` or `amount > 25.00` with `rejected`; keep the single-refill bound fixed and distinct from the configurable epoch cap. (covers: "A single-refill amount outside the bound is rejected"; design D4)
- [x] 2.6 Reject `amount > pnl * 0.10 + 1e-6` with `rejected_exceeds_profit_share`, including under `force`. (covers: "The automatic amount above the profit share is rejected"; "Force does not bypass the profit-share cap"; design D4)
- [x] 2.7 Return `skipped_sufficient_balance` only when `not force` and the balance is above the watermark; `force` must not skip any other check. (covers: "Force bypasses only the low-watermark check"; design D5)
- [x] 2.8 Resolve the epoch cap from `OPENROUTER_MAX_EPOCH_REFILL_USD` (default `$25.00`); replace the process-scoped epoch total with a rolling 24 h deque of `(timestamp_ms, amount_usd)` refill events pruned by `now_ms - timestamp_ms < 86_400_000` under the shared `RLock`; expose `epoch_refilled_usd` as a read-only derived property; reject `epoch_refilled_usd + amount > cap` with `rejected_epoch_cap` and append an event only on a successful refill. (covers: "Profit-share and epoch caps apply on every path"; ADR-0003's `<= $25/24h` invariant; design D20)
- [x] 2.9 Ensure every rejection returns before mutating `openrouter_balance_usd`, the spend window, the epoch window, and `refill_history`; add one assertion per rejection class. (covers: "A rejection does not consume epoch headroom"; "Negative measured PnL on the automatic path performs no refill"; design D4, D20)
- [x] 2.10 Add the gate matrix tests with explicit preconditions: negative/zero PnL at the watermark with auto-refill enabled; forced positive PnL above the watermark; `$0.00`/`$25.01` with PnL `$100`, epoch `$0`, balance at the watermark; amount `$10` with PnL `$50`; a positive control of `$4.00` with PnL `$100`, epoch `$0`, balance at the watermark; a `$23.00` epoch total seeded by prior refills with a `$4.00` request at the default cap and at `$40.00`; an epoch event aged `86_399_999` ms (counts) versus `86_400_000` ms (excluded) with the injected clock; kill switch automatic and forced operator; missing-argument `TypeError`; verbatim reason values. Assert the selected status explicitly in every case. (covers: all gate and epoch scenarios; design D4, D5, D20)

## 3. Rolling 24-hour spend window

- [x] 3.1 Replace the cumulative counter with a `deque[(timestamp_ms, cost_usd)]`; prune entries with age `>= 86_400_000` ms on every record and read; guard record, hydrate, prune, and sum with a dedicated `threading.RLock`. (covers: "Daily spend is a rolling 24-hour window"; "The 24-hour boundary is exclusive"; design D6)
- [x] 3.2 Make `total_cost_usd` a read-only `@property`; remove every assignment in `record_usage` and `hydrate_from_ledger`; direct assignment must raise `AttributeError`. (covers: "The reported total is the window, not lifetime spend"; design D7)
- [x] 3.3 Route `remaining_budget_usd`, `remaining_budget_ratio`, `budget_exhausted`, `get_thinking_depth`, and `get_status` through the window. (covers: "The window works without Redis"; "A long-lived process recovers its budget after rollover"; "Thinking depth recovers after rollover"; design D7)
- [x] 3.4 Remove the `REDIS_URL` conditional and every Redis dependency from spend accounting; the same values must result with `REDIS_URL` unset. (covers: "The window works without Redis"; design D6)
- [x] 3.5 Use the constructor-injected `self._now_ms` (default `int(time.time() * 1000)`) for record, spend-window prune, hydration cutoff, and epoch-window prune; no test patches `time.time`. (covers: exact boundary and rollover determinism; design D12, D20)
- [x] 3.6 Add the window tests: `$4.00` aged `86_400_001` ms excluded; `86_399_999` included and `86_400_000` excluded; `$4.00` then a rolled-over `$1.00` reports `$1.00`; `budget_exhausted` recovers; `DETERMINISTIC_LOCK` returns to `DEEP_THESIS`; no Redis; read-only assignment raises. (covers: all window scenarios; design D6, D7, D12)

## 4. Injectable, lazy, bounded ledger hydration

- [x] 4.1 Resolve the ledger path as constructor argument > non-empty, stripped `COSTGUARD_LEDGER_PATH` > `Path(__file__).resolve().parents[1] / "data" / "transcript_ledger.jsonl"`; an empty or whitespace-only env value is unset; expose the result as `ledger_path`. (covers: "The default path does not depend on the working directory"; design D10)
- [x] 4.2 Remove the `REDIS_URL` hydration call and every construction-time ledger read; constructing with a path whose read raises must succeed. (covers: "Construction performs no ledger read"; design D8)
- [x] 4.3 Add `_ensure_hydrated()` that runs `hydrate_from_ledger()` once, before the first `record_usage` append and on the first daily-spend access; use `_hydrating`/`_hydrated` under the shared `RLock`, set `_hydrating` before the scan, reset it in `finally`, and leave `_hydrated` false on error so it stays observable. A concurrent call blocks until the scan completes; a re-entrant call returns. (covers: lazy hydration; "Construction performs no ledger read"; design D8, D9)
- [x] 4.4 Keep `hydrate_from_ledger(storage_path=None)` public and always executable; an explicit call replaces the spend window (never the epoch refill window), computes its return from the local scan sum (never `self.total_cost_usd`), and is documented as a reseed whose post-record use is a deliberate undercount. (covers: "Repeated hydration does not double count"; design D8, D9)
- [x] 4.5 Implement the reverse chunked scan (64 KiB) of the active file, then `<name>.1`; keep entries while `now_ms - timestamp_ms < 86_400_000` and stop at the first entry whose age is `>= 86_400_000`; document that the early stop assumes monotonically non-decreasing `timestamp_ms`; never call `read_text()` or `splitlines()` on the ledger. (covers: "The rotated segment contributes in-window entries"; "Ledger entries outside the window are ignored"; design D11)
- [x] 4.6 Compute the per-entry cost as `max(cost_usd, compute_call_cost(model, prompt_tokens, completion_tokens))`; retain in-window entries with zero tokens; skip malformed lines; update hydrated tokens, calls, and the usage log. (covers: "The authoritative cost is the larger of recorded and computed"; design D11)
- [x] 4.7 Treat a missing ledger as an empty window with no error; propagate an unreadable existing file only from the lazy or explicit hydration call. (covers: "A missing ledger leaves spend at zero"; design D8)
- [x] 4.8 Pass an isolated temporary `ledger_path` in every test that constructs `OrchestratorAgent` (`test_architecture.py`, `test_hierarchy_v3.py`, `test_integrity_provenance.py`, `test_llm_truncation.py`). (covers: "An isolated ledger path blocks a developer ledger"; design D17)
- [x] 4.9 Add the hydration tests: zero construction reads, a `$50.00` developer ledger isolated by an empty path, CWD independence, an empty `COSTGUARD_LEDGER_PATH` treated as unset, `<name>.1`, `max(cost_usd, computed)`, the exact `86_399_999`/`86_400_000` boundary pair, the scan-order case (an out-of-window entry before an in-window entry) and the late-appended older entry that documents the stop, idempotent repeated hydration, missing file, unreadable file surfaced lazily, no recursion or double seed when the explicit return and the first `total_cost_usd` access are both exercised, a concurrent-call case (one thread runs a slow hydration while another reads `total_cost_usd`; assert a single scan and no double seed), and the absence of `read_text`/`splitlines` in `monitor.py`. (covers: all hydration scenarios; F01, F02, F06, F12, PLAN-R2-F17; design D8–D12)
- [x] 4.10 Add the hydration-before-record test: seed the ledger with `$2.00`, record `$1.00` on a fresh `CostGuard`, and assert the daily spend is `$3.00` (the one-shot hydration preceded the record and did not drop it); on a separate fresh instance, call `hydrate_from_ledger()` twice against the same contents and assert the value is `$2.00` both times, with no double count; then record `$1.00`, call `hydrate_from_ledger()` explicitly, and assert the spend window is `$2.00` (the epoch window is untouched), characterizing the deliberate replacement/undercount. (covers: "Repeated hydration does not double count"; F07; design D9)

## 5. Status contract and operator surface

- [x] 5.1 Confirm `OPENROUTER_LOW_WATERMARK_USD` (default `$2.00`) is the only watermark source used by the automatic trigger, the non-forced gate, `get_status`, and the UI. (covers: "The low watermark has one backend-owned value"; design D14)
- [x] 5.2 Set `auto_wallet_refill` to `ENABLED_PROFIT_GATED` when `auto_refill_enabled` and `DISABLED` otherwise; set `auto_refill_policy` to `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR` or `DISABLED`; delete `DISABLED_BY_SECURITY_POLICY`. (covers: "Auto-refill status labels are truthful"; design D13)
- [x] 5.3 Add `openrouter_credit.measured_pnl_source_available` derived from `self.store is not None`; a store-less `CostGuard` keeps the configuration-driven enum and reports the flag as `false`. Add the bounded `openrouter_credit.last_refill_rejection` object (`status`, `reason`, `timestamp_ms`), set on every gate rejection, on the automatic no-source branch, and by the operator no-source facade, never appended to `refill_history`. (covers: R2 follow-up 4; F11; design D13)
- [x] 5.4 Advance `contract_version` from `2` to `3` in `get_system_status` and update the #7 assertion; record that no existing field is removed or renamed, two additive fields are introduced, and the enum value changes. (covers: migration/consumer note; design D13)
- [x] 5.5 Add the status tests: default `2.00`; configured `3.50` gate boundary at `3.50` and `3.51`; enabled/disabled labels; construction without a store still returns a payload with `ENABLED_PROFIT_GATED` and `measured_pnl_source_available: false`; a rejected automatic refill populates `last_refill_rejection` while `refill_history` stays empty and the label does not change; `epoch_refilled_usd` reflects the rolling epoch window; `contract_version == 3`. (covers: all status, watermark, and rejection-observability scenarios; design D13, D14, D20)
- [x] 5.6 Record the breaking enum migration in the PR body with a `BREAKING CHANGE:` footer and in the issue logbook, naming `ENABLED_PROFIT_GATED`, `DISABLED`, `auto_refill_policy`, `contract_version: 3`, and the two additive fields (`measured_pnl_source_available`, `last_refill_rejection`). (covers: "Auto-refill status labels are truthful"; design D13)

## 6. Frontend watermark

- [x] 6.1 In `frontend/src/components/MasterOverview.jsx`, render `openrouterCredit.low_watermark_usd` directly through `formatOperational`; remove `?? 5.0`; a missing value renders `—`. (covers: "The UI renders the backend watermark"; "The UI renders an em dash for a missing watermark"; design D14)
- [x] 6.2 Add `?? 5.0` to the forbidden patterns in `frontend/scripts/check-provenance.mjs` and assert `formatOperational(undefined, 'money') === '—'`. (covers: UI em dash; design D14)
- [x] 6.3 Leave the `$15` refill button amount unchanged as the approved non-goal; confirm the status still exposes `refill_amount_usd` for the issue #5 follow-up. (covers: design D15; proposal Non-goals)

## 7. ADR-0003 amendment

- [x] 7.1 Amend the auto-refill bullet in `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md`: `$5.00` -> `$2.00`; state the Python gate conditions (PnL > 0, 10 %, fixed `(0, $25.00]` plus the configured epoch cap as a rolling 24 h window, kill switch inactive); name the Rust routing follow-up. (covers: "Refills are refused while the kill switch is active"; "Profit-share and epoch caps apply on every path"; ADR-0003's `<= $25/24h` invariant; design D16, D20)
- [x] 7.2 Add `## Amendment — 2026-10-26 (fix-costguard-python-gate)` recording the watermark rationale, the Python gate ownership until the Rust routing lands, the rolling 24 h epoch window, and the in-memory restart limitation. (covers: ADR deliverable; design D16, D20)
- [x] 7.3 Record the epoch-window persistence-across-restarts follow-up on issue #5 and name the residual limitation in the PR body, so the in-memory restart boundary is on the human decision surface rather than hidden. (covers: F05; design D20)

## 8. Test migration and non-regression

- [x] 8.1 Update `backend/tests/test_architecture.py`: construct with an isolated ledger path, assert `ENABLED_PROFIT_GATED`/`PROFIT_GATED_CAPPED_BY_ORCHESTRATOR` and the `DISABLED` toggle, rename the label test, and keep the hard-cap assertion. (covers: "Auto-refill status labels are truthful"; design D17)
- [x] 8.2 Update `backend/tests/test_hierarchy_v3.py`: replace the `total_cost_usd` assignment with `record_usage` (auto-refill disabled in the helper), fix the `$2.50` comment to `$2.00`, pass an isolated ledger path, update the hydration assertions at `#L316-319` to assert the explicit return equals the local sum and a subsequent `total_cost_usd` access neither recurses nor double-seeds, and keep the profit-gated refill test green. (covers: window and hydration migration; watermark; F01; design D7, D17)
- [x] 8.3 Update `backend/tests/test_integrity_provenance.py`: replace both `_lock_budget` assignments with `record_usage` after setting `auto_refill_enabled = False`, pass isolated ledger paths at every `OrchestratorAgent` construction, update `contract_version` to `3`, and keep the null-safe/measured-only refill tests. For the `SERVER_CHILD_SCRIPT` and `test_missing_binary.CHILD_SCRIPT` subprocesses, create a `TemporaryDirectory` and pass `env={**os.environ, "COSTGUARD_LEDGER_PATH": <tmp>/ledger.jsonl}` to `subprocess.run`; in the integrity `status` scenario assert `payload["cost_guard"]["total_spent_usd"] == 0.0` so a developer ledger cannot be read. (covers: #7 non-regression; F03, F10; design D7, D17)
- [x] 8.4 Update `backend/tests/test_llm_truncation.py` to pass an isolated ledger path. (covers: hermetic suite; design D17)
- [x] 8.5 Create `backend/tests/test_costguard_gate.py` with injection, gate, rolling spend window, rolling epoch window, hydration, status, and automatic-path classes, using a fake `now_ms` clock and temporary ledgers. (covers: every costguard scenario; design D12, D17, D20)
- [x] 8.6 Run the #7/#8a/#9/#10 non-regression suites (`test_integrity_provenance`, `test_policy_ttl_heartbeat`, `test_missing_binary`, `test_contract_*`) and `cargo test`; no Rust, schema, or provenance file changes. (covers: integration with merged changes; design D19)

## 9. Deployment and rollback evidence

- [x] 9.1 Run `docker compose up --build -d`; `docker-compose.yml` has no healthchecks, so wait with `curl --retry 30 --retry-delay 2 --retry-connrefused -fsS http://localhost:8000/api/v1/status` and confirm `docker compose ps --format '{{.Service}} {{.State}}'` reports `running` for `redis`, `backend`, and `frontend`; then assert the status contract (`2.0`, `ENABLED_PROFIT_GATED`, `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR`, `measured_pnl_source_available: true`, `contract_version: 3`) and POST a forced refill on the clean install, expecting a structured rejection and never a `TypeError`. (covers: Docker-as-shipped; status; gate; design D13, D14)
- [x] 9.2 Attach the evidence: new and migrated unit-test output, the Docker status and refill JSON, `npm run lint`, `npm run build`, `check-provenance.mjs`, and the grep gates from `## Verification`. (covers: `## Verification`)
- [x] 9.3 Record the rollback procedure from the design's Migration Plan in the PR body and confirm it restores `DISABLED_BY_SECURITY_POLICY` with the backend watermark `2.0` (the frontend's old `?? 5.0` fallback then displays `$5.00`), with no Redis or ledger cleanup. (covers: rollback requirement; F04)

## Verification

Run from the repository root (the worktree root) unless a step changes directory.

- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` -> expected: the binary builds; the Python integration suite requires it.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_costguard_gate -v` -> expected: every injection, gate, window, hydration, status, and automatic-path test passes.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_architecture backend.tests.test_hierarchy_v3 backend.tests.test_integrity_provenance backend.tests.test_llm_truncation -v` -> expected: all pass, including the migrated `total_cost_usd` and status-label assertions.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` -> expected: the full warm-path suite passes with no error or failure.
- `cd engine-rs && cargo test` -> expected: all Rust tests pass; no file under `engine-rs/` is modified by this change.
- `cd frontend && npm run lint` -> expected: exit 0.
- `cd frontend && npm run build` -> expected: the Rolldown build succeeds and writes `dist/`.
- `cd frontend && node scripts/check-provenance.mjs` -> expected: `provenance wiring OK`; the script fails if `?? 5.0` returns or the em-dash assertion regresses.
- `git grep -nE 'max\(125\.0' -- backend` -> expected: no output (exit 1).
- `git grep -n 'DISABLED_BY_SECURITY_POLICY' -- backend` -> expected: no output (exit 1).
- `git grep -n 'state_store' -- backend/agents/monitor.py` -> expected: no output (exit 1); there is no module-global measured source.
- `git grep -n 'REDIS_URL' -- backend/agents/monitor.py` -> expected: no output (exit 1); spend accounting is Redis-independent.
- `git grep -nE 'read_text|splitlines' -- backend/agents/monitor.py` -> expected: no output (exit 1); hydration streams the ledger.
- `git grep -nE 'total_cost_usd\s*=' -- backend/agents/monitor.py` -> expected: no output (exit 1); the aggregate is a read-only property.
- `git grep -nE 'epoch_refilled_usd\s*=' -- backend/agents/monitor.py` -> expected: no output (exit 1); the epoch total is a read-only derived window.
- `git grep -n 'hydrate_from_ledger' -- backend/agents backend/server.py` -> expected: only the method definition and the `_ensure_hydrated()` call in `monitor.py`; no other production call site.
- `git grep -n '?? 5\.0' -- frontend/src/components/MasterOverview.jsx` -> expected: no output (exit 1).
- `git grep -n 'DISABLED_BY_SECURITY_POLICY\|low_watermark_usd = \$5\.00' -- docs/adr/0003-hierarchical-multi-ecosystem-architecture.md` -> expected: no output (exit 1).
- `openspec validate fix-costguard-python-gate --strict` -> expected: `Change 'fix-costguard-python-gate' is valid`.
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` -> expected: `spec-lint` PASS and `verdict-lint` PASS.
- `docker compose up --build -d` -> expected: the command returns; `docker-compose.yml` declares no healthchecks, so readiness is checked next.
- `docker compose ps --format '{{.Service}} {{.State}}'` -> expected: `redis running`, `backend running`, `frontend running`.
- `curl --retry 30 --retry-delay 2 --retry-connrefused -fsS http://localhost:8000/api/v1/status >/dev/null` -> expected: exit 0 once the backend answers.
- `curl -s http://localhost:8000/api/v1/status | python3 -c 'import json,sys
d=json.load(sys.stdin)
cg=d["cost_guard"]; credit=cg["openrouter_credit"]
assert d["contract_version"] == 3, d.get("contract_version")
assert credit["low_watermark_usd"] == 2.0, credit["low_watermark_usd"]
assert cg["auto_wallet_refill"] == "ENABLED_PROFIT_GATED", cg["auto_wallet_refill"]
assert cg["auto_refill_policy"] == "PROFIT_GATED_CAPPED_BY_ORCHESTRATOR", cg["auto_refill_policy"]
assert credit["measured_pnl_source_available"] is True, credit["measured_pnl_source_available"]
assert credit["last_refill_rejection"] is None or isinstance(credit["last_refill_rejection"], dict), credit["last_refill_rejection"]
assert "epoch_refilled_usd" in credit, credit
print("costguard status OK")'` -> expected: `costguard status OK`.
- `curl -s -X POST http://localhost:8000/api/v1/openrouter/refill -H 'Content-Type: application/json' -d '{"force": true}' | python3 -c 'import json,sys
d=json.load(sys.stdin)
assert d.get("status") != "rejected_no_pnl_source", d
assert d.get("status") in {"rejected_no_realized_profit","rejected_exceeds_profit_share","rejected_epoch_cap","refilled"}, d
assert "openrouter_balance_usd" in d, d
print("refill endpoint structured: " + d["status"])'` -> expected: a structured status and no `TypeError`; a clean volume reports `rejected_no_realized_profit`.
- Attach to the issue or PR: `evidence/costguard-gate.txt`, `evidence/costguard-hydration.txt`, `evidence/costguard-status.txt`, `evidence/docker-status.json`, `evidence/docker-refill.json`, `evidence/frontend-build.txt`, and `evidence/check-provenance.txt`.
