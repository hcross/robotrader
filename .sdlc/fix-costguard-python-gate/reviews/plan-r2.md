# PLAN Review — Round 2 (closure)

## Summary

APPROVE at `ad721ce260e568f64fbc5a95002ad2148106cfe7`. All 15 R1 findings are closed: hydration is re-entrant-safe under a shared `RLock` with a local scan sum; the cutoff is `now_ms - timestamp_ms < 86_400_000` with the exact `86_399_999` / `86_400_000` pair tested; the `backend.server` subprocesses receive an isolated `COSTGUARD_LEDGER_PATH` and assert `total_spent_usd == 0.0`; rollback expects `DISABLED_BY_SECURITY_POLICY 2.0`; and the epoch is a rolling `(timestamp_ms, amount_usd)` window with rollover and boundary tests, documented in the ADR amendment deliverable. No open or regressed blocker/major. Two new minor regression-origin follow-ups: the traceability table cites a spec requirement the approved spec does not contain, and the design promises a concurrent-call test that task 4.9 does not include. `openspec validate` and `sdlc.sh check` pass; the spec is unchanged since `1ef4c63`.

## Rulings requested by the brief

### F05 — in-memory epoch window: acceptable as a documented follow-up, not in scope now

The window is now a rolling 24 h deque of `(timestamp_ms, amount_usd)` (design D20, `design.md#L113`), pruned with the same exclusive boundary and exposed as a read-only property. A restart opens a new in-memory window; that limitation is named in the Non-Goals (`design.md#L86`), D20, the ADR amendment content (`design.md#L202`), the risk table (`design.md#L238`), task 7.3 (`tasks.md#L68`), and the PR-body requirement. **Ruling: acceptable for this change; persistence need not be in scope now**, for four reasons:

1. The approved spec fixes the epoch cap and its enforcement, not a persistence mechanism; it is silent on restart behaviour. The durable `<= $25/24h` promise comes from ADR-0003, which this change amends explicitly.
2. The change strictly improves the status quo: the pre-change accumulator never rolled over at all, while the new window rolls within the process.
3. The primary capital controls — strictly positive measured PnL, the 10 % share, the fixed `(0, $25.00]` bound, and the kill switch — are per-call and do not reset on restart. The epoch window is a secondary headroom cap; the simulated balance itself also resets on restart, and a real `/credits` balance is an explicit non-goal.
4. Persisting the window would require a Redis schema or a file store, both excluded by the proposal's non-goals and D18; adding persistence now would need a new spec round for the storage contract.

If the operator wants a durable `$25/24h` guarantee, task 7.3 / issue #5 is the vehicle.

### `contract_version` 2 → 3 and the two additive status fields: justified and documented

The bump is required by the breaking `auto_wallet_refill` enum change (`DISABLED_BY_SECURITY_POLICY` removed; `ENABLED_PROFIT_GATED` / `DISABLED` introduced), which the proposal marks **BREAKING** and `sdlc/checklists/plan.md` §3 requires to be versioned. It is documented in D13 (`design.md#L198`), task 5.4 (`tasks.md#L54`) and task 5.6 (`tasks.md#L56`).

The two additive fields are also justified: `measured_pnl_source_available` answers spec-r2 non-blocking follow-up 4 (the no-source state must be observable), and `last_refill_rejection` answers R1 F11 (rejections are otherwise silent, and the spec forbids a refill-history event). Neither removes or renames an existing field, and the same bump covers both. Residual wording follow-up: `proposal.md#L66` still says the status "keeps its shape"; that is a SPEC-stage artifact the PLAN author may not edit, so it is recorded below rather than reopened.

## Checklist walk (`sdlc/checklists/plan.md`)

| Section | Result | Evidence |
|---|---|---|
| 1. Traceability | PASS (F16 follow-up) | All 11 `costguard` requirements and the `integrity` requirement map to tasks in the design traceability table and the task `covers:` annotations. No task changes spec behaviour beyond the R1-authorized rolling epoch window and the two additive observability fields. F16: the epoch row cites a requirement name absent from the spec. |
| 2. Decisions | PASS | D1–D20 name alternatives and technical rejections; D18 keeps the standard library only; D20 records the in-memory trade-off; the contract move is reversible via the rollback. |
| 3. Contracts and data | PASS | `PolicyEnvelope`, Redis IPC, and DB schemas are untouched; the status change is versioned `2 → 3` with a consumer migration note; the ledger is read-only; no cross-chain or cross-venue data. |
| 4. Hot path and performance | PASS | Warm path only; no Rust, `HardRiskGate`, vault, Kelly, dry-powder, or chain-isolation change; the spend and epoch deques are bounded by 24 h; the reverse scan is bounded to 64 KiB chunks and the in-window tail. |
| 5. Safety and security | PASS | Fail-closed no-source paths; kill switch first; no fabricated floor; every rejection returns before mutating balance, epoch, or history; the epoch restart residual is documented (F05 ruling); no secrets or key material. |
| 6. Test strategy | PASS (F17 follow-up) | Every spec scenario has a named test task or verification command; exact-boundary, rollover, scan-order, empty-env, missing/unreadable-ledger, no-recursion, and no-double-seed cases are tasked. F17: the design's promised concurrency test is not in task 4.9. |
| 7. Rollout and rollback | PASS | Deployment order is explicit; rollback is a concrete revert plus a status assertion of `DISABLED_BY_SECURITY_POLICY 2.0`; readiness uses `docker compose ps` + `curl --retry` because no healthchecks exist; `last_refill_rejection` supplies the missing observability. |
| 8. Tasks | PASS | 53 checkboxes in 9 dependency-ordered groups; `## Verification` is root-runnable and produces observable evidence; no hidden spec change beyond the documented epoch rollover and additive fields. |

## Prior findings — status at `ad721ce`

| ID | Severity | Status | Closure evidence |
|---|---|---|---|
| PLAN-R1-F01 | major | closed | `design.md#L165` specifies `_hydrating`/`_hydrated` under the shared `RLock`, sets `_hydrating` before the scan, computes `hydrated_cost_usd` from the local scan sum (never `self.total_cost_usd`), sets `_hydrated` after success, resets `_hydrating` in `finally`, leaves `_hydrated` false on error, and characterizes concurrent (blocks) and re-entrant (returns) calls. Tasks 4.3 (`tasks.md#L40`), 4.4 (`#L41`), 4.9 (`#L46`), 8.2 (`#L73`) add the guard, the return contract, the no-recursion/no-double-seed test, and the `test_hierarchy_v3.py#L316-319` update. |
| PLAN-R1-F02 | major | closed | `design.md#L62,L104` and `tasks.md#L42,L46` use `now_ms - timestamp_ms < 86_400_000` and stop at the first entry with age `>= 86_400_000`; D6 (`design.md#L155-157`) states the same half-open interval; task 4.9 adds the exact `86_399_999` / `86_400_000` hydration pair. The current `monitor.py#L132,L147` boundary is replaced. |
| PLAN-R1-F03 | major | closed | `tasks.md#L74` (8.3) creates a `TemporaryDirectory` and passes `env={**os.environ, "COSTGUARD_LEDGER_PATH": <tmp>/ledger.jsonl}` to both the `SERVER_CHILD_SCRIPT` (`test_integrity_provenance.py#L1079-1084`) and `test_missing_binary.CHILD_SCRIPT` (`test_missing_binary.py#L266-272`) subprocesses, and asserts `payload["cost_guard"]["total_spent_usd"] == 0.0`. Verified the status payload carries `cost_guard` (`server.py#L147`) and `total_spent_usd` (`monitor.py#L427`). |
| PLAN-R1-F04 | major | closed | `design.md#L257-258` rollback step 4 now expects `DISABLED_BY_SECURITY_POLICY 2.0`; step 3 explains the old frontend `?? 5.0` fallback; `tasks.md#L83` (9.3) records the corrected expectation. The pre-change default is `2.00` (`monitor.py#L105-107`). |
| PLAN-R1-F05 | major | closed | D20 (`design.md#L113`) replaces the process-scoped accumulator with a rolling `(timestamp_ms, amount_usd)` deque pruned by `now_ms - timestamp_ms < 86_400_000`, exposes `epoch_refilled_usd` read-only, and appends only on a successful refill. Tasks 2.8 (`tasks.md#L23`), 2.10 (`#L25`), 3.5 (`#L33`), and 7.1–7.3 (`#L66-68`) implement, test, amend ADR-0003, and record the restart follow-up on issue #5. The persistence ruling is above. |
| PLAN-R1-F06 | minor | closed | `design.md#L104,L167,L229` states the monotonic non-decreasing `timestamp_ms` assumption required by the early stop and names the late-appended older entry limitation; task 4.9 (`tasks.md#L46`) adds the out-of-window-before-in-window scan-order test and the late-appended old-entry case. |
| PLAN-R1-F07 | minor | closed | `design.md#L169` states that an explicit reseed after records is a deliberate undercount with no production caller; task 4.10 (`tasks.md#L47`) adds the record-then-explicit-hydrate characterization; the Verification (`tasks.md#L104`) adds `git grep -n 'hydrate_from_ledger' -- backend/agents backend/server.py` with the expected definition + `_ensure_hydrated()` call. |
| PLAN-R1-F08 | minor | closed | Task 2.10 (`tasks.md#L25`) now supplies per-scenario preconditions (measured PnL, balance, `force`, seeded epoch total, env cap) for the bound, profit-share, positive-control, epoch-cap, and force branches and requires asserting the selected status explicitly, so a mis-set-up test fails the assertion instead of passing the wrong branch. |
| PLAN-R1-F09 | minor | closed | D1's signature block (`design.md#L120-124`) includes `now_ms: Optional[Callable[[], int]] = None`, stored as `self._now_ms` with the `int(time.time() * 1000)` default; task 1.1 (`tasks.md#L7`) adds the parameter; task 3.5 (`#L33`) uses it for record, spend-window prune, hydration cutoff, and epoch-window prune. |
| PLAN-R1-F10 | minor | closed | Task 8.3 (`tasks.md#L74`) sets `auto_refill_enabled = False` in `_lock_budget` before replacing the direct assignments with `record_usage`, mirroring task 8.2, so the reflection tests cannot enter the automatic refill branch. |
| PLAN-R1-F11 | minor | closed | D13 (`design.md#L186,L196`) adds the bounded `openrouter_credit.last_refill_rejection` object (`status`, `reason`, `timestamp_ms`), set on every gate rejection, the automatic no-source branch, and the operator no-source facade, never appended to `refill_history`. Tasks 5.3 (`tasks.md#L53`) and 5.5 (`#L55`) implement and test it while asserting the history stays empty and the label unchanged. |
| PLAN-R1-F12 | minor | closed | `design.md#L163` and task 4.1 (`tasks.md#L38`) treat an empty or whitespace-only `COSTGUARD_LEDGER_PATH` as unset, so `Path(".")` cannot reintroduce CWD dependence; task 4.9 (`#L46`) adds the empty-override test. |
| PLAN-R1-F13 | minor | closed | The injected-store precedence test now lives in task 1.4 (`tasks.md#L10`), which owns the automatic-branch rewrite; tasks 1.3 and 1.4 are independently verifiable in the listed order. |
| PLAN-R1-F14 | minor | closed | `design.md#L249` and task 9.1 (`tasks.md#L81`) use `docker compose ps --format '{{.Service}} {{.State}}'` plus `curl --retry 30 --retry-delay 2 --retry-connrefused -fsS`; the Verification (`tasks.md#L109-111`) does the same. `docker-compose.yml` has no healthchecks and its services are `redis`, `backend`, `frontend`, matching the expected output. |
| PLAN-R1-F15 | nit | closed | D13's migration note (`design.md#L198`) and task 5.4 (`tasks.md#L54`) now say: no field removed or renamed; two additive fields; the enum value changes; `contract_version` is 3. Residual: `proposal.md#L66` still says "keeps its shape" (SPEC-stage artifact; follow-up below). |

Counts: 15 closed, 0 open, 0 regressed among prior findings.

## New findings (allowed origins only)

### PLAN-R2-F16 — [minor] The traceability table cites a spec requirement that does not exist

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L215`; `openspec/changes/fix-costguard-python-gate/tasks.md#L23,L66`; `openspec/changes/fix-costguard-python-gate/specs/costguard/spec.md#L81-113`
- Evidence: `grep -rn "The epoch cap rolls over every 24 hours" openspec/changes/fix-costguard-python-gate/specs` returns no match. The approved spec's epoch requirement is "Profit-share and epoch caps apply on every path", which fixes the cap but not a 24 h window; the rolling `<= $25/24h` promise comes from `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30`. The R1 design had no such traceability row (it treated the rollover as a non-goal); the row and the two `covers:` annotations were introduced by the R1 correction. The behaviour itself is the R1-F05-authorized improvement and is not unsafe.
- Required fix: Reword the traceability row and the `covers:` annotations to cite the actual spec requirement plus ADR-0003's `<= $25/24h` invariant (or add the requirement in a spec round if a durable spec statement is desired). No behaviour change is required.
- Status: open (non-blocking)
- Origin: regression

### PLAN-R2-F17 — [minor] The design promises a concurrent-call test that task 4.9 does not include

- Location: `openspec/changes/fix-costguard-python-gate/design.md#L230`; `openspec/changes/fix-costguard-python-gate/tasks.md#L46` (4.9)
- Evidence: The risk table says "a concurrent-call test asserts one scan", but `grep -n "concurrent-call test" openspec/changes/fix-costguard-python-gate/tasks.md` returns no match; task 4.9 lists the no-recursion/no-double-seed test but no multi-threaded case. The promise was added in the revision (the R1 design contains no such line).
- Required fix: Add the concurrent-call test to task 4.9 (for example, one thread triggers a slow hydration while another reads `total_cost_usd`; assert one ledger scan and no double seed), or remove the promise from the risk table.
- Status: open (non-blocking)
- Origin: regression

## Follow-ups (non-blocking, not verdict findings)

- **F08 setup detail.** Task 2.10's forced-refill and epoch-cap cases do not pin the PnL, balance, and `force` values as explicitly as the other cases; the "assert the selected status" requirement makes a wrong branch fail, but DEV should pin them.
- **F09 summary row.** The D1 table row still shows `LLMMonitorAgent(store=None, ledger_path=None)` without `now_ms`; the detailed signature block has it. Cosmetic.
- **F15 proposal wording.** `proposal.md#L66` still says the status "keeps its shape" while two additive fields are introduced. SPEC-stage artifact; the plan author cannot edit it.
- **Task 8.5 ordering.** The new `test_costguard_gate.py` is created in task 8.5, after tasks 2.10/3.6/4.9/5.5 that add tests; the module can be created earlier or 8.5 can be phrased as the consolidation step. Not a behaviour or coverage gap.
- **Epoch window requirement.** See F16; no behaviour change needed.

## Checks run

- `git rev-parse HEAD` → `ad721ce260e568f64fbc5a95002ad2148106cfe7`.
- `openspec validate fix-costguard-python-gate --strict` → `Change 'fix-costguard-python-gate' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` → `check: PASS`; `spec-lint` PASS (Review Card 172 words, 1 diagram, ~1.4 min; 53 open tasks); `verdict-lint` PASS for spec-r1/spec-r2/plan-r1.
- `git diff --stat 1ef4c63..HEAD -- openspec/changes/fix-costguard-python-gate/specs openspec/changes/fix-costguard-python-gate/proposal.md` → empty: the approved spec is unchanged.
- `git diff 8282c38..HEAD -- design.md tasks.md` → reviewed in full; no spec change, only the R1 corrections.
- `grep -c '^- \[ \]' tasks.md` → 53; `grep -c '^### Requirement:' specs/costguard/spec.md` → 11; `grep -c '^#### Scenario:' ...` → 46.
- `grep -rn "The epoch cap rolls over every 24 hours" .../specs` → no match (F16).
- `grep -n "concurrent-call test" .../tasks.md` → no match (F17).
- Source checks: `monitor.py#L105-107` (watermark `2.00`), `#L132,L147` (current cutoff includes the exact boundary), `#L180` (current return reads `self.total_cost_usd`), `#L427` (`total_spent_usd` in status); `server.py#L41` (`OrchestratorAgent(store=state_store)` with no `ledger_path`), `#L106-112` and `#L147` (`/api/v1/status` returns `cost_guard`); `test_integrity_provenance.py#L1079-1084` and `test_missing_binary.py#L266-272` (subprocesses currently omit `env`); `test_hierarchy_v3.py#L316-319` (existing hydration assertion); `docker-compose.yml` (services `redis`/`backend`/`frontend`, no healthcheck); `frontend/src/components/MasterOverview.jsx#L401` (`?? 5.0`); `backend/core/transcript_palace.py#L56,L313` (`time.time()` append); `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30` (`$5.00`, `<= $25/24h`).
- Scope: this review wrote only `.sdlc/fix-costguard-python-gate/reviews/plan-r2.md`; no design, tasks, spec, code, or issue edit.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-costguard-python-gate",
  "stage": "plan",
  "round": 2,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "ad721ce260e568f64fbc5a95002ad2148106cfe7",
  "verdict": "APPROVE",
  "summary": "All 15 R1 findings are closed at ad721ce: hydration is re-entrant-safe under RLock with a local scan sum, the cutoff is age < 86,400,000 ms with the exact pair tested, the server subprocesses are ledger-isolated and assert total_spent_usd == 0.0, rollback expects DISABLED_BY_SECURITY_POLICY 2.0, and the epoch is a tested rolling 24 h window documented in the ADR amendment. Zero open blocker/major. Two new minor regression-origin follow-ups remain: a traceability row cites a spec requirement absent from the approved spec, and a promised concurrent-call test is not tasked. The in-memory epoch restart limitation is acceptable as a documented, issue-tracked follow-up.",
  "findings": [
    {
      "id": "PLAN-R2-F16",
      "severity": "minor",
      "origin": "regression",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L215; tasks.md#L23,L66; specs/costguard/spec.md#L81-113",
      "evidence": "grep -rn 'The epoch cap rolls over every 24 hours' openspec/changes/fix-costguard-python-gate/specs returns no match; the approved spec's epoch requirement is 'Profit-share and epoch caps apply on every path' and the rolling <= $25/24h promise is ADR-0003#L30. The R1 design had no such traceability row; the revision introduced it and the two covers: annotations.",
      "required_fix": "Reword the traceability row and the covers: annotations to cite the actual spec requirement plus ADR-0003's <= $25/24h invariant, or add the requirement in a spec round. No behaviour change."
    },
    {
      "id": "PLAN-R2-F17",
      "severity": "minor",
      "origin": "regression",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md#L230; tasks.md#L46 (4.9)",
      "evidence": "The risk table promises 'a concurrent-call test asserts one scan', but grep -n 'concurrent-call test' tasks.md returns no match and task 4.9 lists no multi-threaded case; the promise was added by the revision.",
      "required_fix": "Add the concurrent-call test to task 4.9 (one thread triggers a slow hydration, another reads total_cost_usd; assert one scan and no double seed) or remove the promise from the risk table."
    }
  ],
  "closed": [
    "PLAN-R1-F01",
    "PLAN-R1-F02",
    "PLAN-R1-F03",
    "PLAN-R1-F04",
    "PLAN-R1-F05",
    "PLAN-R1-F06",
    "PLAN-R1-F07",
    "PLAN-R1-F08",
    "PLAN-R1-F09",
    "PLAN-R1-F10",
    "PLAN-R1-F11",
    "PLAN-R1-F12",
    "PLAN-R1-F13",
    "PLAN-R1-F14",
    "PLAN-R1-F15"
  ]
}
```
