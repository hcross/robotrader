## 1. Refill gate contract

- [ ] 1.1 Make `realized_trading_pnl_usd` a required argument of the refill entry point; a call that omits it fails before any state mutation (covers: `Every refill path requires a measured realized PnL` / "A refill call without a realized PnL cannot execute").
- [ ] 1.2 Wire the automatic path in `record_usage` to the state store's measured realized PnL helper, with no local default and no floor (covers: "The automatic path supplies the measured store value", `No fabricated profit floor`).
- [ ] 1.3 Keep the REST refill endpoint on the same measured helper and reject a negative or zero value before evaluating the amount (covers: "The operator path supplies the measured store value", `A refill requires strictly positive realized profit`).
- [ ] 1.4 Ensure a zero or negative PnL rejection leaves the balance, epoch refilled total, and refill history untouched (covers: "A rejection does not consume epoch headroom").
- [ ] 1.5 Apply the 10% profit-share cap, the `(0, $25.00]` single-refill bound, and the `$25.00` epoch cap on the automatic path (covers: `Profit-share and epoch caps apply on every path`).
- [ ] 1.6 Verify the two `max(125.0, pnl)` floor expressions remain absent from `backend/` (covers: `No fabricated profit floor`; #7 non-regression).

## 2. Rolling 24-hour spend window

- [ ] 2.1 Replace the cumulative `total_cost_usd` accounting with a rolling window of per-call `(timestamp_ms, cost_usd)` entries whose age is strictly below `86,400,000` ms (covers: `Daily spend is a rolling 24-hour window` / "Spend older than 24 hours is excluded").
- [ ] 2.2 Enforce the exclusive 24-hour boundary at exactly `86,400,000` ms (covers: "The 24-hour boundary is exclusive").
- [ ] 2.3 Make `remaining_budget_usd`, `budget_exhausted`, `get_status`, and `get_thinking_depth` read the same window while `REDIS_URL` is unset (covers: "The window works without Redis", "A long-lived process recovers its budget after rollover", "Thinking depth recovers after rollover").
- [ ] 2.4 Rework `hydrate_from_ledger` to replace the window contents from in-window ledger rows, idempotently (covers: "Repeated hydration does not double count", "Ledger entries outside the window are ignored").
- [ ] 2.5 Invoke hydration at `CostGuard` initialization whenever `backend/data/transcript_ledger.jsonl` exists, independent of `REDIS_URL` (covers: "A restart without Redis reconstructs the window", "A missing ledger leaves spend at zero").

## 3. Low watermark and status surface

- [ ] 3.1 Keep `OPENROUTER_LOW_WATERMARK_USD` (default `$2.00`) as the only watermark source and confirm the trigger and `get_status` both read it (covers: `The low watermark has one backend-owned value` / "The status and the trigger share the configured value").
- [ ] 3.2 Remove the `?? 5.0` fallback in `frontend/src/components/MasterOverview.jsx` and render `openrouterCredit.low_watermark_usd`, with a non-numeric unavailable marker when absent (covers: "The UI renders the backend watermark", "The UI does not fabricate a missing watermark").
- [ ] 3.3 Replace the `auto_wallet_refill: "DISABLED_BY_SECURITY_POLICY"` value with `ENABLED_PROFIT_GATED` when auto-refill is enabled and `DISABLED` otherwise; make `auto_refill_policy` follow the same state (covers: `Auto-refill status labels are truthful`).

## 4. Regression tests

- [ ] 4.1 Add an automatic-path test that sets the balance at or below the low watermark, supplies `-$10.00` measured PnL through the store, and asserts no refill event and an unchanged balance (covers: "The negative-PnL automatic test passes").
- [ ] 4.2 Add a zero-PnL automatic-path test and a positive control within the profit-share and epoch caps (covers: "The zero-PnL automatic test passes", "The positive control refills").
- [ ] 4.3 Add window tests for rollover, the exact boundary, no-Redis operation, and idempotent hydration (covers: `Daily spend is a rolling 24-hour window`, `Ledger hydration seeds the rolling window`).
- [ ] 4.4 Update the existing label assertion in `backend/tests/test_architecture.py` and the watermark comment in `backend/tests/test_hierarchy_v3.py` to the new truthful values (covers: `Auto-refill status labels are truthful`, low-watermark single source).

## 5. Documentation and deployment check

- [ ] 5.1 Update the CostGuard section of `AGENTS.md` if the status field semantics change, keeping the "no unbounded refills" invariant stated (covers: `Auto-refill status labels are truthful`).
- [ ] 5.2 Run the full backend suite, the frontend build, and the Docker stack, and attach the evidence to the PR (covers: `## Verification`).

## Verification

- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: all tests pass, including the new automatic-path negative/zero PnL tests.
- `PYTHONPATH=. python3 -m unittest backend.tests.test_architecture backend.tests.test_hierarchy_v3 -v` → expected: updated status-label and refill tests pass.
- `grep -rn "max(125.0" backend/` → expected: no output.
- `grep -n "DISABLED_BY_SECURITY_POLICY" backend/agents/monitor.py` → expected: no output.
- `grep -n "?? 5.0" frontend/src/components/MasterOverview.jsx` → expected: no output.
- `cd frontend && npm run build` → expected: build succeeds.
- `cd engine-rs && cargo test` → expected: all Rust tests pass (unchanged; regression guard).
- `docker compose up --build -d` then `curl -s http://localhost:8000/api/v1/status | jq '.cost_guard.openrouter_credit.low_watermark_usd, .cost_guard.auto_wallet_refill'` → expected: `2.0` and `"ENABLED_PROFIT_GATED"`.
- `openspec validate fix-costguard-python-gate --strict` → expected: validation passes.
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` → expected: spec-lint passes with no errors.
