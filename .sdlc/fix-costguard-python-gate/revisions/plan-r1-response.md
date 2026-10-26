stage: plan
round: 1
head_sha: 8282c38597f918f9f92a7c5813a9d69150412ccd
responses:
  - id: PLAN-R1-F01
    action: fixed
    evidence: >-
      Design D8/D9 now state the re-entrancy and return contract: `_hydrating`
      and `_hydrated` are guarded by the shared `RLock`; the scan sets
      `_hydrating` before reading, replaces only the spend window, computes
      `hydrated_cost_usd` from the local scan sum (never `self.total_cost_usd`),
      sets `_hydrated` after success, resets `_hydrating` in `finally`, and
      leaves `_hydrated` false on error. No hydration path reads an aggregate
      property. A concurrent call blocks on the lock; a re-entrant call returns.
      Task 4.3 adds the guard, task 4.4 fixes the return contract, task 4.9 adds
      the no-recursion/no-double-seed test, and task 8.2 updates the existing
      `test_hierarchy_v3.py#L316-319` assertions.
  - id: PLAN-R1-F02
    action: fixed
    evidence: >-
      Design D11 and the hydration flow diagram now keep an entry while
      `now_ms - timestamp_ms < 86_400_000` and stop at the first entry whose age
      is `>= 86_400_000`; the exact-boundary exclusion is the same predicate as
      the runtime window (D6). Task 4.5 uses the `>=` wording, and task 4.9 adds
      the exact `86_399_999` (included) / `86_400_000` (excluded) hydration pair.
  - id: PLAN-R1-F03
    action: fixed
    evidence: >-
      Task 8.3 now requires a `TemporaryDirectory` and
      `env={**os.environ, "COSTGUARD_LEDGER_PATH": "<tmp>/ledger.jsonl"}` for
      both `SERVER_CHILD_SCRIPT` (`test_integrity_provenance`) and `CHILD_SCRIPT`
      (`test_missing_binary`) subprocesses, and asserts
      `payload["cost_guard"]["total_spent_usd"] == 0.0` in the integrity `status`
      scenario, so a developer ledger cannot be read by the child.
  - id: PLAN-R1-F04
    action: fixed
    evidence: >-
      Design rollback step 4 now expects `DISABLED_BY_SECURITY_POLICY 2.0`,
      matching the pre-change `OPENROUTER_LOW_WATERMARK_USD` default. Step 3
      states that the old frontend `?? 5.0` fallback will display `$5.00` and
      that this is a UI fallback, not the backend watermark. Task 9.3 records the
      corrected expectation.
  - id: PLAN-R1-F05
    action: fixed
    evidence: >-
      Implemented the 24 h epoch rollover in the plan. Design D20 replaces the
      process-scoped accumulator with a `(timestamp_ms, amount_usd)` deque,
      pruned by `now_ms - timestamp_ms < 86_400_000` under the shared `RLock`,
      with `epoch_refilled_usd` as a read-only derived property and an append
      only on a successful refill. D16 and the Non-Goals now state the rolling
      window and the in-memory restart limitation; task 7.3 records the
      persistence-across-restarts follow-up on issue #5. Tasks 2.8, 2.10, and 3.5
      implement and test the rollover, including the exact boundary and a
      clock-advanced refill after the old event ages out.
  - id: PLAN-R1-F06
    action: fixed
    evidence: >-
      Design D11 now states the monotonic non-decreasing `timestamp_ms`
      assumption required by the early stop, and the risk table names the
      late-appended older entry limitation. Task 4.9 adds the scan-order test
      (an out-of-window entry before an in-window entry) and the late-appended
      old-entry case that documents the stop.
  - id: PLAN-R1-F07
    action: fixed
    evidence: >-
      Design D9 states that an explicit reseed after records is a deliberate
      undercount with no production caller. Task 4.10 adds the
      record-then-explicit-hydrate characterization test (the window falls back
      to the ledger sum). The Verification adds
      `git grep -n 'hydrate_from_ledger' -- backend/agents backend/server.py`
      with the expected output limited to the definition and the
      `_ensure_hydrated()` call.
  - id: PLAN-R1-F08
    action: fixed
    evidence: >-
      Task 2.10 now gives the per-scenario preconditions: measured PnL, balance,
      `force`, seeded epoch total, and env cap for each gate branch, and requires
      asserting the selected rejection status explicitly. This covers the
      bound, profit-share, positive-control, epoch-cap, and force scenarios
      without falling into `rejected_no_realized_profit` or
      `skipped_sufficient_balance`.
  - id: PLAN-R1-F09
    action: fixed
    evidence: >-
      Design D1's signature now includes
      `now_ms: Optional[Callable[[], int]] = None`, stored as `self._now_ms` with
      the `int(time.time() * 1000)` default. Task 1.1 adds the parameter, and
      task 3.5 requires the constructor clock for record, spend-window prune,
      hydration cutoff, and epoch-window prune.
  - id: PLAN-R1-F10
    action: fixed
    evidence: >-
      Task 8.3 now sets `auto_refill_enabled = False` in `_lock_budget` before
      calling `record_usage`, mirroring task 8.2, so the reflection tests cannot
      run the automatic refill branch or mutate refill state mid-test.
  - id: PLAN-R1-F11
    action: fixed
    evidence: >-
      Design D13 adds a bounded `openrouter_credit.last_refill_rejection`
      object with `status`, `reason`, and `timestamp_ms`; it is set on every gate
      rejection, the automatic no-source branch, and the operator no-source
      facade, and is never appended to `refill_history`. Task 5.3 implements it,
      and task 5.5 asserts that a rejected automatic refill populates it while
      the history stays empty and the label does not change.
  - id: PLAN-R1-F12
    action: fixed
    evidence: >-
      Design D10 and task 4.1 treat an empty or whitespace-only
      `COSTGUARD_LEDGER_PATH` as unset, so `Path(".")` cannot reintroduce CWD
      dependence. Task 4.9 adds the empty-override test.
  - id: PLAN-R1-F13
    action: fixed
    evidence: >-
      The injected-store precedence test moved from task 1.3 to task 1.4, which
      owns the automatic-branch rewrite. Tasks 1.3 and 1.4 are now independently
      verifiable in dependency order.
  - id: PLAN-R1-F14
    action: fixed
    evidence: >-
      Task 9.1 and the Verification now use `docker compose ps --format
      '{{.Service}} {{.State}}'` and
      `curl --retry 30 --retry-delay 2 --retry-connrefused -fsS` against
      `/api/v1/status`, because `docker-compose.yml` declares no healthchecks.
      "Healthy" is no longer the expected evidence; readiness is.
  - id: PLAN-R1-F15
    action: fixed
    evidence: >-
      Design D13's migration note now reads: no existing field is removed or
      renamed; two additive fields are introduced
      (`measured_pnl_source_available`, `last_refill_rejection`); the
      `auto_wallet_refill` enum value changes; `contract_version` is `3`. Task
      5.4 carries the same wording.
