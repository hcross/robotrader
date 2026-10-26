# PLAN Review — Round 1

## Summary

CHANGES_REQUESTED at `8282c38`: five majors, nine minors, one nit, zero blockers. The architecture is sound and traces to the approved spec: constructor injection with fail-closed `rejected_no_pnl_source`, the kill-switch → PnL → caps → watermark → epoch gate order, a rolling deque window, lazy bounded hydration, truthful status, and a backend-rendered watermark. Five majors block execution: (1) lazy-hydration re-entrancy and the `hydrate_from_ledger` return/property recursion are unspecified; (2) the reverse-scan cutoff wording can include the `86,400,000` ms entry the spec excludes; (3) the in-process server subprocess tests are not ledger-isolated; (4) the rollback expects `$5.00` where the pre-change backend returns `2.0`; (5) the process-scoped epoch narrows ADR-0003's `$25/24h` without a decision or follow-up task. `openspec validate` and `sdlc.sh check` pass; the spec is unchanged.

## Rulings on the four stated risks

1. **`contract_version` 2 → 3 and `measured_pnl_source_available` — justified, not a hidden spec change.** The spec-r2 reviewer's non-blocking follow-up 4 explicitly asks for the no-source state to be clarified; the proposal declares the `auto_wallet_refill` enum change **BREAKING** and requires a migration; `sdlc/checklists/plan.md` §3 requires a contract change to be versioned. The readiness flag is additive, and the bump marks the enum break. Only the wording "the rest of the status shape is unchanged" is inaccurate (F15). No spec round is required.
2. **Process-scoped epoch accumulator — not acceptable as-is for a capital-protection path.** The spec is silent on the 24 h epoch rollover and the code is already process-scoped, so this is not a code regression; but the plan amends ADR-0003's documented `<= $25/24h` guarantee to "process-scoped", the proposal's *Decision needed* names only the watermark and kill-switch, and no task records the epoch follow-up on issue #5. A restart therefore permits another full epoch cap while the human decision surface does not name the trade-off. Either implement the rollover (small, spec-compatible) or escalate the narrowed guarantee and task the issue follow-up (F05).
3. **Inverted ledger scan — assumption written, test not tasked.** D11 and the risk table state the append-ordered assumption, and `TranscriptPalace` appends with `time.time()` under a single writer. However, the risk table promises a test that writes an out-of-window entry before an in-window entry, while task 4.9 only says "in/out-of-window entries"; the design also never says "monotonically non-decreasing timestamps". Add the ordering test and state the stronger assumption (F06).
4. **Explicit re-hydration reset — spec-mandated, documented, but not guarded.** The spec requires repeated hydration to replace the window, so a reseed is intended; the one-shot lazy path runs before the first record and the orchestrator writes the ledger after `record_usage` (verified at all four call sites). But task 4.10 tests repeated hydration only on a fresh instance, not record-then-explicit-hydrate, and no verification gate asserts that production calls `hydrate_from_ledger` only through `_ensure_hydrated`. Characterize the reset and add the call-site gate (F07).

## Checklist walk (sdlc/checklists/plan.md)

| Section | Result | Evidence |
|---|---|---|
| 1. Traceability | PASS | Every `costguard` and `integrity` requirement maps to tasks in the design traceability table; D19 preserves #7/#8a/#9/#10; the spec at `1ef4c63` is unchanged. F05 is the epoch decision-surface gap; F15 is a wording nit. |
| 2. Decisions | PASS | D1–D19 name alternatives and technical rejections; no new dependency (D18); the contract/rollback makes the decisions reversible. The epoch non-goal is a safety trade-off, not a missing alternative (F05). |
| 3. Contracts and data | PASS | `PolicyEnvelope`, IPC, Redis, and DB are untouched; the `auto_wallet_refill` enum break is versioned `2 → 3` with a consumer migration note; no data migration; hydration is read-only. F15: the "shape unchanged" wording is inaccurate. |
| 4. Hot path and performance | PASS | Warm path only; no Rust, `HardRiskGate`, vault, Kelly, dry-powder, or chain-isolation change. The deque is bounded by the 24 h window; the reverse scan is bounded by in-window entries and 64 KiB chunks; no allocation/logging on the hot path. |
| 5. Safety and security | FAIL | The profit gate, kill switch, and rolling window strengthen capital protection; but the epoch guarantee is narrowed without a decision (F05), and automatic refill rejections remain silent (F11). No vault/secret exposure. |
| 6. Test strategy | FAIL | Unit, gate-matrix, hydration, status, and Docker smoke tests are planned; F01 (re-entrancy), F02 (exclusive boundary), F03 (subprocess isolation), F06 (scan ordering), F07 (reseed), and F08 (gate preconditions) leave scenarios under-specified. |
| 7. Rollout and rollback | FAIL | Deployment order and a concrete revert procedure exist; F04 gives a wrong expected pre-change watermark, and F14 expects "healthy" from a compose file with no healthchecks. Observability is limited to successful refills (F11). |
| 8. Tasks | FAIL | 52 checkboxes in 9 dependency-ordered groups; `## Verification` is root-runnable and produces observable evidence. F13 is a wrong intra-group dependency (1.3's test requires 1.4); F14 is a verification-accuracy gap. |

## Findings

### PLAN-R1-F01 — [major] Lazy hydration can recurse or double-seed because the re-entrancy and return contract are unspecified

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L101-102,L158-165` (D8/D9), `openspec/changes/fix-costguard-python-gate/tasks.md#L40,L47` (4.3/4.4), `backend/agents/monitor.py#L176-180`
- Evidence: The current `hydrate_from_ledger` returns `{"hydrated_calls": calls_cnt, "hydrated_cost_usd": self.total_cost_usd}` (`monitor.py#L180`). The plan makes `total_cost_usd` a property that triggers `_ensure_hydrated()` on first spend access (D7/D8) but never states when `_hydrated` is set. A natural implementation (`if not self._hydrated: self.hydrate_from_ledger(); self._hydrated = True`) recurses: `hydrate_from_ledger` reads `self.total_cost_usd`, the property calls `_ensure_hydrated`, the flag is still false, and hydration re-enters. Even without the return read, any property access during hydration is unsafe. Task 4.4 preserves the public method but not its return contract, and task 8.2 does not mention the existing assertion at `backend/tests/test_hierarchy_v3.py#L316-319`.
- Required fix: Specify the re-entrancy contract in D8/D9: set `_hydrated` (or a `_hydrating` sentinel) before the read, reset it to false on error, and compute `hydrated_cost_usd` from the local scan sum rather than `self.total_cost_usd`. Add a test that the explicit call's return value and the first `total_cost_usd` access neither recurse nor double-seed, and update the existing hierarchy test.
- Status: open
- Origin: initial

### PLAN-R1-F02 — [major] The hydration cutoff wording can include the entry aged exactly `86,400,000` ms

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L62,L104` (hydration flow, D11), `openspec/changes/fix-costguard-python-gate/tasks.md#L42,L46` (4.5/4.9), `openspec/changes/fix-costguard-python-gate/specs/costguard/spec.md#L248-251`; `backend/agents/monitor.py#L132,L147`
- Evidence: The spec requires an entry aged exactly `86,400,000` ms to be excluded, and the hydration scenario asserts one entry aged `86,399,999` ms and one aged `86,400,000` ms contribute only the younger. D11 says the scan "stops ... at the first entry older than the cutoff"; task 4.5 repeats "older than the cutoff". The current code defines `cutoff_ms = now - 86_400_000` and keeps `ts < cutoff_ms` (`monitor.py#L132,L147`), which includes `ts == cutoff_ms` (age exactly `86,400,000`). Task 4.9 only says "in/out-of-window entries"; the exact hydration boundary is asserted only for the runtime window in task 3.6.
- Required fix: Define the hydration predicate as `now_ms - ts < 86_400_000` (exclude age `>= 86_400_000`), align the D11/task 4.5 wording ("at or older than the cutoff"), and add the exact `86,399,999` / `86,400,000` pair to task 4.9's hydration tests.
- Status: open
- Origin: initial

### PLAN-R1-F03 — [major] The in-process server subprocess tests are not ledger-isolated

- Location: `openspec/changes/fix-costguard-python-gate/tasks.md#L45,L73` (4.8/8.3), `openspec/changes/fix-costguard-python-gate/specs/costguard/spec.md#L220`; `backend/tests/test_integrity_provenance.py#L937,L1079-1084`; `backend/tests/test_missing_binary.py#L183,L266-272`; `backend/server.py#L41`
- Evidence: The spec requires the test suite to inject an isolated ledger path so a developer ledger cannot alter the suite's initial spend. The plan injects paths into direct `OrchestratorAgent(...)` constructions, but `SERVER_CHILD_SCRIPT` (`test_integrity_provenance.py#L937`) and `CHILD_SCRIPT` (`test_missing_binary.py#L183`) import `backend.server`, which constructs `OrchestratorAgent(store=state_store)` with no `ledger_path` (`server.py#L41`); both `subprocess.run` calls omit `env` (`test_integrity_provenance.py#L1079-1084`, `test_missing_binary.py#L266-272`). The integrity "status" scenario calls `/api/v1/status`, whose `cost_guard.get_status()` triggers lazy hydration of `backend/data/transcript_ledger.jsonl`; a developer ledger (or an unreadable one) can alter the child's initial spend and fail the test.
- Required fix: Set `COSTGUARD_LEDGER_PATH` to an isolated temporary path in the child environment for every subprocess that imports `backend.server` (or add a test-only override), and assert the child's initial spend is `0.0` in the status scenario. Add the child-env step to task 8.3.
- Status: open
- Origin: initial

### PLAN-R1-F04 — [major] The rollback verification expects `$5.00` where the pre-change backend returns `2.0`

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L246-248` (Migration Plan, rollback steps 3-4), `openspec/changes/fix-costguard-python-gate/tasks.md#L82` (9.3); `backend/agents/monitor.py#L105-107`; `frontend/src/components/MasterOverview.jsx#L401`
- Evidence: Rollback step 4 runs the status endpoint and says it prints `DISABLED_BY_SECURITY_POLICY 5.0`; the pre-change `LLMMonitorAgent` defaults `low_watermark_usd` to `$2.00` from `OPENROUTER_LOW_WATERMARK_USD` (`monitor.py#L105-107`), and `get_status` returns that value. `$5.00` is only the current frontend fallback (`?? 5.0`, `MasterOverview.jsx#L401`). The rollback check would fail on a default deployment and mislead the operator about whether rollback succeeded.
- Required fix: Change the expected output to `DISABLED_BY_SECURITY_POLICY 2.0`; note that the frontend will display `$5.00` only because of the old `?? 5.0` fallback; update task 9.3's confirmation and the design's rollback text.
- Status: open
- Origin: initial

### PLAN-R1-F05 — [major] The process-scoped epoch narrows ADR-0003's `$25/24h` guarantee without a decision or follow-up task

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L86,L195` (Non-Goals, D16), `openspec/changes/fix-costguard-python-gate/tasks.md#L66-67` (7.1/7.2); `openspec/changes/fix-costguard-python-gate/proposal.md#L10,L52-59`; `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30`
- Evidence: ADR-0003 promises `<= $25/24h`; the plan keeps `epoch_refilled_usd` process-scoped and amends the ADR to say so. The proposal's *Decision needed* names only the `$5.00 → $2.00` watermark and the kill-switch condition; the epoch scope is not in the proposal's non-goals; and the design's non-goal says the gap is recorded "in the ADR amendment and the issue", while task 7.2 records it only in the ADR. A restart therefore permits another full epoch cap, and the human decision surface is asked to approve an ADR amendment that narrows a capital-protection guarantee without that trade-off named.
- Required fix: Either implement the 24 h epoch rollover in this change (reuse `now_ms` with an epoch start marker; the spec does not forbid it) and add a rollover test, or escalate as `safety-ambiguity`/`scope-change` with the narrowed guarantee in the decision, and add an explicit task to record the follow-up on issue #5. Do not silently reword the ADR.
- Status: open
- Origin: initial

### PLAN-R1-F06 — [minor] The reverse-scan ordering assumption is stated but the promised ordering test is not tasked

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L104,L220` (D11, risk table), `openspec/changes/fix-costguard-python-gate/tasks.md#L46` (4.9)
- Evidence: The risk table says "a test writes an out-of-window entry before an in-window entry and asserts the in-window value"; task 4.9 only says "in/out-of-window entries", without the ordering or the assertion. The design also says "append-ordered" but not "monotonically non-decreasing timestamps", which is the property the early stop actually requires; a late-appended old-timestamp entry would stop the scan before older in-window entries.
- Required fix: State the monotonic non-decreasing timestamp assumption explicitly in D11, and add the ordering test to task 4.9 (out-of-window entry before an in-window entry, plus a late-appended old entry case).
- Status: open
- Origin: initial

### PLAN-R1-F07 — [minor] Explicit re-hydration reset is documented but not characterized or guarded

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L102,L221` (D9, risk table), `openspec/changes/fix-costguard-python-gate/tasks.md#L41,L47` (4.4/4.10)
- Evidence: The spec mandates replace semantics, and D9 says production calls hydration only through the one-shot lazy path before recording. Task 4.10 tests repeated hydration only on a fresh instance; it does not test record-then-explicit-hydrate, which drops the in-memory record and understates spend. No verification gate asserts that production has no other `hydrate_from_ledger` call site after the `__init__` call is removed.
- Required fix: Add a characterization test that records after lazy hydration and then explicitly re-hydrates, asserting the replacement semantics; add a `git grep` gate that the only production caller is `_ensure_hydrated`; and state in D9 that an explicit reseed after records is a deliberate undercount with no production caller.
- Status: open
- Origin: initial

### PLAN-R1-F08 — [minor] Task 2.10's gate matrix omits the balance/force/PnL/epoch preconditions

- Location: `openspec/changes/fix-costguard-python-gate/tasks.md#L25` (2.10), `openspec/changes/fix-costguard-python-gate/design.md#L97` (D4); `.sdlc/fix-costguard-python-gate/reviews/spec-r2.md` follow-up 6
- Evidence: The gate order is kill switch → positive PnL → bound → profit share → watermark unless `force` → epoch cap. The bound scenarios need positive PnL to reach the `rejected` branch; the epoch-cap and `$4.00` positive-control scenarios need positive PnL (`>= $40` for a `$4` share), an epoch total, and either `force` or a balance at/below the watermark. Task 2.10 lists the scenarios without those preconditions, so a test can hit `rejected_no_realized_profit` or `skipped_sufficient_balance` and assert the wrong branch. The spec-r2 reviewer flagged exactly this as follow-up 6.
- Required fix: Add the per-scenario preconditions (measured PnL, balance, `force`, epoch total, env cap) to task 2.10 and assert the selected rejection status explicitly.
- Status: open
- Origin: initial

### PLAN-R1-F09 — [minor] The `now_ms` injection point is unspecified

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L105,L119` (D12, D1 signature), `openspec/changes/fix-costguard-python-gate/tasks.md#L33` (3.5)
- Evidence: D12 requires an injectable `now_ms` clock and rejects patching `time.time`, but the D1 constructor signature is `LLMMonitorAgent(name, daily_budget_usd, store, ledger_path)` with no `now_ms`; task 1.1 adds only `store` and `ledger_path`; task 3.5 says "Add an injectable `now_ms` clock" without saying whether it is a constructor parameter, a settable attribute, or a method argument. The window/hydration boundary tests cannot be written deterministically until this is fixed.
- Required fix: Add `now_ms: Optional[Callable[[], int]] = None` to the D1 signature and task 1.1 (stored as `self._now_ms`), and have task 3.5 use it for record, prune, and hydration.
- Status: open
- Origin: initial

### PLAN-R1-F10 — [minor] The migrated `_lock_budget` helper should disable auto-refill

- Location: `openspec/changes/fix-costguard-python-gate/tasks.md#L72-73` (8.2/8.3); `backend/tests/test_integrity_provenance.py#L725-727`
- Evidence: Task 8.2 explicitly says "auto-refill disabled in the helper" for `test_hierarchy_v3.py`, but task 8.3 replaces `_lock_budget`'s direct `total_cost_usd` assignment with `record_usage` without disabling auto-refill. `record_usage` decrements `openrouter_balance_usd` and runs the automatic branch, so these reflection tests now exercise the refill gate unintentionally; a store with positive measured PnL and a low balance could mutate state mid-test.
- Required fix: Set `self.orchestrator.cost_guard.auto_refill_enabled = False` in `_lock_budget` before recording, or assert the gate outcome explicitly; mirror task 8.2's wording in task 8.3.
- Status: open
- Origin: initial

### PLAN-R1-F11 — [minor] Automatic refill rejections have no observability

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L77,L189` (Goals, status contract), `openspec/changes/fix-costguard-python-gate/tasks.md#L55` (5.5); `openspec/changes/fix-costguard-python-gate/specs/costguard/spec.md#L55`
- Evidence: The spec forbids appending a refill-history event on rejection, so a negative-PnL, kill-switch, or cap rejection on the automatic path leaves no trace: `record_usage` discards the gate result and returns `get_status()`, and the plan adds `measured_pnl_source_available` only for the no-source case. An operator cannot tell why auto-refill is not happening on a path whose only purpose is capital protection.
- Required fix: Add a non-history status field (for example `openrouter_credit.last_refill_rejection` with status/reason/timestamp) or a bounded log line, and a status test; or declare the omission an explicit non-goal with the operator workaround.
- Status: open
- Origin: initial

### PLAN-R1-F12 — [minor] An empty `COSTGUARD_LEDGER_PATH` resolves to the process working directory

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L103` (D10), `openspec/changes/fix-costguard-python-gate/tasks.md#L38` (4.1)
- Evidence: D10 resolves the path as "constructor argument > `COSTGUARD_LEDGER_PATH` > module-anchored default". If the environment variable is present but empty (a common compose/Helm artifact, matching the existing empty-string `REDIS_URL` handling), a `Path(os.getenv(...))` implementation yields `Path(".")`, reintroducing CWD dependence and raising `IsADirectoryError` on the first spend access. The spec's CWD-independence scenario does not cover an empty override.
- Required fix: Treat an empty/whitespace `COSTGUARD_LEDGER_PATH` as unset (like `os.getenv("REDIS_URL", "").strip()`), and add a test for the empty override.
- Status: open
- Origin: initial

### PLAN-R1-F13 — [minor] Task 1.3's test depends on task 1.4's behaviour

- Location: `openspec/changes/fix-costguard-python-gate/tasks.md#L9-10` (1.3/1.4)
- Evidence: Task 1.3 adds a test that the injected store's `-$10.00` (not a different global store's `$100.00`) produces no refill. The automatic path in `record_usage` still calls `trigger_openrouter_refill` **without** the PnL until task 1.4 rewrites the branch, so the gate's PnL check is skipped and the balance-at-watermark case refills. Running task 1.3's test before task 1.4 fails; the group's stated order is 1.1, 1.2, 1.3, 1.4.
- Required fix: Move the injected-store test to task 1.4 (or reorder 1.4 before 1.3) so every task is independently verifiable.
- Status: open
- Origin: initial

### PLAN-R1-F14 — [minor] The compose verification expects "healthy" from a compose file with no healthchecks

- Location: `openspec/changes/fix-costguard-python-gate/tasks.md#L106` (Verification), `openspec/changes/fix-costguard-python-gate/design.md#L238` (Migration Plan); `docker-compose.yml`
- Evidence: `docker-compose.yml` declares no `healthcheck` for `backend` or `frontend`; `docker compose up --build -d` returns before either service is ready. The Verification's expected "backend and frontend containers healthy" is therefore unverifiable, and the following `curl` can race the backend start. 
- Required fix: Replace "healthy" with an observable readiness check (`docker compose ps` state plus `curl --retry`/`--retry-connrefused` on `/api/v1/status`), or add healthchecks to the compose file; state the wait in task 9.1.
- Status: open
- Origin: initial

### PLAN-R1-F15 — [nit] The design says "the rest of the status shape is unchanged" while adding a field

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L189-191` (D13 migration note), `openspec/changes/fix-costguard-python-gate/proposal.md#L66`
- Evidence: The plan adds `openrouter_credit.measured_pnl_source_available` (an additive field) and changes the `auto_wallet_refill` enum value, then bumps `contract_version` to `3`; "the rest of the status shape is unchanged" and the proposal's "keeps its shape" can be read as "no new field". The substantive ruling is that the additive field is justified by spec-r2 follow-up 4 and the version bump by the breaking enum; only the wording is inaccurate.
- Required fix: Reword the migration note to "no existing field is removed or renamed; one additive field (`measured_pnl_source_available`); the enum value changes; `contract_version` is 3".
- Status: open
- Origin: initial

## Checks run

- `git rev-parse HEAD` -> `8282c38597f918f9f92a7c5813a9d69150412ccd`.
- `openspec validate fix-costguard-python-gate --strict` -> "Change 'fix-costguard-python-gate' is valid", exit 0.
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` -> PASS; `spec-lint` PASS (Review Card 172 words, 1 diagram, ~1.4 min; 52 open tasks), `verdict-lint` PASS for spec-r1/spec-r2.
- Independent inspection: `backend/agents/monitor.py` (lines 91, 105-107, 118-180, 295-332, 342-415, 443-454), `backend/agents/orchestrator.py` (lines 36-52, 560-595), `backend/server.py` (lines 41, 107-152, 259-265), `backend/core/state_store.py` (lines 91, 883-901), `backend/core/transcript_palace.py` (lines 86-120), `frontend/src/components/MasterOverview.jsx` (lines 62-63, 205, 397-402), `frontend/src/lib/provenance.js`, `frontend/scripts/check-provenance.mjs`, `docker-compose.yml`, and the four test modules.
- Confirmed: `hydrate_from_ledger` returns `self.total_cost_usd` (`monitor.py#L180`); `cutoff_ms`/`ts < cutoff_ms` includes age exactly `86,400,000` (`monitor.py#L132,L147`); the server child subprocesses inherit the environment without `COSTGUARD_LEDGER_PATH` (`test_integrity_provenance.py#L1079-1084`, `test_missing_binary.py#L266-272`); the pre-change watermark default is `2.00` (`monitor.py#L105-107`); `TranscriptPalace` appends and rotates at 100 MB (`transcript_palace.py#L95,L113-120`); the orchestrator writes the transcript after `record_usage` at all four call sites.
- Scope: the approved spec at `1ef4c63` is unchanged; no design/tasks/code/spec edit was made by this review.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-costguard-python-gate",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "8282c38597f918f9f92a7c5813a9d69150412ccd",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Five majors and nine minors remain: lazy hydration can recurse or double-seed because the re-entrancy and hydrate return contract are unspecified; the reverse-scan cutoff can include the 86,400,000 ms entry the spec excludes; the server subprocess tests are not ledger-isolated; the rollback expects $5.00 where the pre-change backend returns 2.0; and the process-scoped epoch narrows ADR-0003's $25/24h without a decision or follow-up task. Injection, gate order, rolling window, status, and frontend design are otherwise sound and spec-traceable.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L101-102,L158-165; tasks.md#L40,L47; backend/agents/monitor.py#L176-180",
      "evidence": "hydrate_from_ledger returns {'hydrated_cost_usd': self.total_cost_usd}; the plan makes total_cost_usd a property that calls _ensure_hydrated but never says when _hydrated is set. A natural implementation recurses (property -> ensure -> hydrate -> property) or double-seeds, and task 8.2 ignores the existing assertion at test_hierarchy_v3.py#L316-319.",
      "required_fix": "Specify the re-entrancy contract: set _hydrated/_hydrating before the read, reset on error, and compute hydrated_cost_usd from the local sum. Add a no-recursion/no-double-seed test and update the hierarchy test."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L62,L104; tasks.md#L42,L46; specs/costguard/spec.md#L248-251; backend/agents/monitor.py#L132,L147",
      "evidence": "The spec excludes the entry aged exactly 86,400,000 ms, but D11/task 4.5 say 'older than the cutoff' and the current code uses cutoff = now - 86_400_000 with ts < cutoff, which includes ts == cutoff. Task 4.9 does not assert the exact hydration boundary.",
      "required_fix": "Define hydration as now_ms - ts < 86_400_000 (exclude age >= 86_400_000), align the wording, and add the 86_399_999/86_400_000 pair to task 4.9."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/tasks.md#L45,L73; specs/costguard/spec.md#L220; backend/tests/test_integrity_provenance.py#L937,L1079-1084; backend/tests/test_missing_binary.py#L183,L266-272; backend/server.py#L41",
      "evidence": "The server child scripts import backend.server, which constructs OrchestratorAgent(store=state_store) with no ledger_path, and both subprocess.run calls omit env. The integrity status scenario calls /api/v1/status, whose get_status triggers lazy hydration of the developer ledger.",
      "required_fix": "Set COSTGUARD_LEDGER_PATH to an isolated temp path in the child environment for every subprocess importing backend.server, and assert initial spend is 0.0; add this to task 8.3."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L246-248; tasks.md#L82; backend/agents/monitor.py#L105-107; frontend/src/components/MasterOverview.jsx#L401",
      "evidence": "Rollback step 4 expects the status to print DISABLED_BY_SECURITY_POLICY 5.0, but the pre-change backend default is 2.00 from OPENROUTER_LOW_WATERMARK_USD; 5.00 is only the frontend ?? 5.0 fallback.",
      "required_fix": "Change the expected output to DISABLED_BY_SECURITY_POLICY 2.0, note the frontend fallback, and update task 9.3."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L86,L195; tasks.md#L66-67; proposal.md#L10,L52-59; docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30",
      "evidence": "ADR-0003 promises <= $25/24h; the plan keeps the epoch process-scoped and amends the ADR to say so. The proposal's Decision needed names only the watermark and kill-switch, and task 7.2 records the epoch gap only in the ADR, not on issue #5. A restart permits another full epoch cap while the human decision surface does not name the trade-off.",
      "required_fix": "Implement the 24h epoch rollover with a test, or escalate safety-ambiguity/scope-change with the narrowed guarantee in the decision and add an explicit issue #5 follow-up task."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L104,L220; tasks.md#L46",
      "evidence": "The risk table promises a test with an out-of-window entry before an in-window entry, but task 4.9 only says 'in/out-of-window entries'. The design also does not state the monotonic non-decreasing timestamp property the early stop requires.",
      "required_fix": "State the monotonic timestamp assumption in D11 and add the ordering test (including a late-appended old entry) to task 4.9."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L102,L221; tasks.md#L41,L47",
      "evidence": "The spec mandates replace semantics and D9 documents the reseed, but task 4.10 tests repeated hydration only on a fresh instance, not record-then-explicit-hydrate, and no verification gate asserts that _ensure_hydrated is the only production caller.",
      "required_fix": "Add a record-then-explicit-hydrate characterization test, a grep gate for production call sites, and state the deliberate undercount in D9."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/tasks.md#L25; design.md#L97; .sdlc/fix-costguard-python-gate/reviews/spec-r2.md (follow-up 6)",
      "evidence": "The gate order is kill switch, positive PnL, bound, profit share, watermark unless force, epoch cap. Task 2.10 lists the bound, epoch-cap, and positive-control scenarios without the PnL, balance, force, or epoch-total preconditions, so a test can assert the wrong branch.",
      "required_fix": "Add the per-scenario preconditions and assert the selected rejection status explicitly in task 2.10."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L105,L119; tasks.md#L33",
      "evidence": "D12 requires an injectable now_ms and rejects patching time.time, but the D1 constructor signature and task 1.1 omit now_ms; task 3.5 does not say whether it is a constructor parameter or attribute.",
      "required_fix": "Add now_ms: Optional[Callable[[], int]] = None to the D1 signature and task 1.1, and use it in task 3.5."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/tasks.md#L72-73; backend/tests/test_integrity_provenance.py#L725-727",
      "evidence": "Task 8.2 disables auto-refill in the hierarchy helper, but task 8.3 replaces _lock_budget with record_usage without disabling it; record_usage then runs the automatic refill branch and may mutate state mid-test.",
      "required_fix": "Set auto_refill_enabled = False in _lock_budget before recording, mirroring task 8.2."
    },
    {
      "id": "PLAN-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L77,L189; tasks.md#L55; specs/costguard/spec.md#L55",
      "evidence": "The spec forbids a refill-history entry on rejection; record_usage discards the gate result and the plan adds no non-history rejection observable, so a negative-PnL, kill-switch, or cap rejection on the automatic path is silent.",
      "required_fix": "Add a non-history status field (status/reason/timestamp) or a bounded log line and a status test, or declare the omission a non-goal."
    },
    {
      "id": "PLAN-R1-F12",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L103; tasks.md#L38",
      "evidence": "An empty COSTGUARD_LEDGER_PATH resolves to Path('.') under a naive implementation, reintroducing CWD dependence and raising IsADirectoryError on the first spend access; the existing REDIS_URL handling strips empty values.",
      "required_fix": "Treat an empty/whitespace COSTGUARD_LEDGER_PATH as unset and add a test for the empty override."
    },
    {
      "id": "PLAN-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/tasks.md#L9-10",
      "evidence": "Task 1.3's injected-store test requires task 1.4's automatic-branch rewrite; before 1.4 the gate is called without the PnL and the balance-at-watermark case refills, so the test fails if run in the listed order.",
      "required_fix": "Move the injected-store test to task 1.4, or reorder 1.4 before 1.3."
    },
    {
      "id": "PLAN-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/tasks.md#L106; design.md#L238; docker-compose.yml",
      "evidence": "docker-compose.yml has no healthchecks; docker compose up --build -d returns before readiness, so the Verification's expected 'backend and frontend containers healthy' is unverifiable and the following curl can race.",
      "required_fix": "Use docker compose ps plus a curl --retry readiness check, or add healthchecks, and state the wait in task 9.1."
    },
    {
      "id": "PLAN-R1-F15",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L189-191; proposal.md#L66",
      "evidence": "The plan adds measured_pnl_source_available and changes the enum, then bumps contract_version, while saying 'the rest of the status shape is unchanged'. The additive field is justified by spec-r2 follow-up 4 and the bump by the breaking enum; the wording is inaccurate.",
      "required_fix": "Reword to: no existing field removed or renamed; one additive field; the enum value changes; contract_version is 3."
    }
  ],
  "closed": []
}
```
