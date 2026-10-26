# SPEC Review — Round 1

## Summary

CHANGES_REQUESTED. The intent is sound — measured PnL required on every refill path, no fabricated floor, a Redis-independent rolling 24 h window, one backend watermark, truthful status, and automatic-path regression coverage — and all three automated checks pass. Four majors block approval: the change looks like a capital-protection Lane L change yet is Lane S with no `design.md` or PLAN review; it contradicts accepted ADR-0003's `$5.00` low watermark while mandating `$2.00` with "no decision needed"; it requires "the state store's" PnL on the automatic path but `LLMMonitorAgent` holds no store, so wiring and fail-closed behaviour are undefined; and construction-time hydration from the fixed dev ledger makes the suite non-hermetic and can read a 100 MB file synchronously. Minors cover the undocumented `$15`/`$10` refill-button mismatch, integrity-spec overlap, epoch-cap configurability, force semantics, and unobservable automatic-path assertions.

## Findings

### SPEC-R1-F01 — [major] Change is a money/capital-protection path but is authored as Lane S

- Location: `.sdlc/fix-costguard-python-gate/state.json#L6`; `sdlc/PROTOCOL.md#L54-62`; `openspec/config.yaml#L19-20`
- Evidence: `state.json` records `"lane": "S"` with reason "Backend-only CostGuard slice; 4-7 files; no Rust gate ownership decision". PROTOCOL §2.1 assigns Lane L to any "Money, risk, vault, key, or execution-routing path"; `config.yaml` lists "`CostGuard` daily cap, no unbounded refills" under the capital-protection invariant. The delta changes the refill gate and the daily-spend accounting. Lane S therefore omits `design.md` and PLAN review for a money-path change.
- Required fix: upgrade to Lane L (autonomous per PROTOCOL §2.1), record `lane_change` in `state.json` and the issue, add `design.md` (diagram, decision table, risks/rollback), and route through PLAN review; or record a written human-approved Lane S exception.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] Low-watermark default contradicts accepted ADR-0003 and is declared decision-free

- Location: `openspec/changes/fix-costguard-python-gate/specs/costguard/spec.md#L167-169`; `proposal.md#L10`; `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30`
- Evidence: ADR-0003 (Status: Accepted) states "Monitors the OpenRouter credit balance (`low_watermark_usd = $5.00`)"; the delta mandates "defaulting to `$2.00`"; the Review Card says "Decision needed: None. Scope is fixed by the partial-change comment on issue #5." The ADR's gate also includes "kill-switch inactive", which the delta's three caps omit and the Non-goals do not name specifically.
- Required fix: reconcile explicitly — either amend ADR-0003 to `$2.00` with the rationale and add the ADR to `Impact`, or adopt `$5.00`; and state the ADR's kill-switch condition as an explicit requirement or an explicit non-goal. Remove "Decision needed: None" if the reconciliation is a decision.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] Automatic path cannot reach "the state store's" measured PnL as specified

- Location: `specs/costguard/spec.md#L5`; `backend/agents/monitor.py#L66,L75-119,L295-332`; `backend/agents/orchestrator.py#L43`; `backend/tests/test_integrity_provenance.py#L723,L810`
- Evidence: `LLMMonitorAgent` has no store reference; `record_usage` is where the automatic refill fires (`monitor.py#L327`); `OrchestratorAgent` constructs it with only `name="CostGuard"` (`orchestrator.py#L43`). Tests inject a per-test `HybridStateStore` into the orchestrator (`test_integrity_provenance.py#L723,L810`), while `server.py#L262` uses the module-global `state_store`; a dev reading the global from `monitor.py` would evaluate the wrong PnL. The spec never defines the store instance, the injection mechanism, or the no-store failure path.
- Required fix: state that the orchestrator injects its own store (constructor argument or callable) into the `CostGuard`, that the automatic path calls that instance's `measured_realized_pnl_usd()`, and that an absent measured source performs no refill (fail closed). Add a scenario for the missing-source case.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] Construction-time hydration from the fixed dev ledger is non-hermetic and unbounded

- Location: `specs/costguard/spec.md#L142-144`; `backend/agents/monitor.py#L118-128`; `backend/tests/test_architecture.py#L28-34`; `backend/tests/test_hierarchy_v3.py#L22-25`; `backend/core/transcript_palace.py#L95,L115`
- Evidence: the requirement mandates hydration "from `backend/data/transcript_ledger.jsonl` whenever that file exists, regardless of whether `REDIS_URL` is set". That file is gitignored and dev-local. `test_architecture.py#L28-34` constructs `OrchestratorAgent` and asserts `budget_exhausted` is false at startup without isolating the path; `test_hierarchy_v3.py#L22-25` patches `transcript_palace.storage_path`, which the `CostGuard` hydration does not use. The ledger rotates at `MAX_JSONL_BYTES = 100_000_000` (`transcript_palace.py#L95`), so construction can synchronously read up to 100 MB. Local runs after using the app become order- and environment-dependent.
- Required fix: make the ledger path injectable at construction (constructor argument or environment override) with the current path as default, and require the test suite to pass an isolated temporary path. Add a scenario asserting that a pre-existing dev ledger does not alter the suite's initial spend, and state the construction read-cost bound.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [minor] UI refill button `$15` vs backend `$10` is neither in scope nor an explicit non-goal

- Location: `frontend/src/components/MasterOverview.jsx#L205`; `backend/agents/monitor.py#L108-110`; `proposal.md#L48-54`
- Evidence: the UI posts `{ amount_usd: 15.0, force: true }`; the backend's `OPENROUTER_REFILL_AMOUNT_USD` defaults to `10.00`. The change modifies this same card and single-sources the watermark, but the Non-goals never mention the refill amount, so the boundary around it is undefined.
- Required fix: add an explicit Non-goals bullet (follow-up on issue #5), or render `openrouter_credit.refill_amount_usd` from the status and use it for the button label and payload.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [minor] Proposal wrongly claims no existing spec defines CostGuard behaviour

- Location: `proposal.md#L44-46`; `openspec/specs/integrity/spec.md#L264-266`; `specs/costguard/spec.md#L5,L13-17`
- Evidence: the proposal says "None. No existing spec under `openspec/specs/` defines CostGuard behavior." `openspec/specs/integrity/spec.md#L264-266` is a requirement "Refill gating consumes null-safe measured PnL only" that names the REST and Master-reflection callers, forbids the `max(125.0, …)` floor, and defers the remaining CostGuard defects to issue #5. The new `costguard` delta restates the operator-path rule without declaring a MODIFIED delta.
- Required fix: reference the integrity requirement and either scope the new capability to the remaining defects, or add a `## MODIFIED Requirements` block that copies the full integrity requirement and states the change.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [minor] Epoch cap hardcoded to `$25.00` although it is configured

- Location: `specs/costguard/spec.md#L61,L77`; `backend/agents/monitor.py#L111-113`
- Evidence: the requirement and scenario fix the epoch cap at `$25.00`; the code resolves `OPENROUTER_MAX_EPOCH_REFILL_USD` (default `25.00`). The single-refill bound `(0, $25.00]` is hardcoded and is a different constraint.
- Required fix: state the epoch cap as the configured value (`OPENROUTER_MAX_EPOCH_REFILL_USD`, default `$25.00`) and keep the fixed single-refill bound distinct.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [minor] "Every refill trigger MUST compare" collides with operator `force`

- Location: `specs/costguard/spec.md#L169`; `backend/agents/monitor.py#L382-387`; `frontend/src/components/MasterOverview.jsx#L205`
- Evidence: the operator button sends `force: true`, and the gate deliberately skips the watermark when `force` is set (`if not force and balance > low_watermark`). A literal implementation of "every refill trigger MUST compare the credit balance against that same value" would refuse on-demand recharges above the watermark.
- Required fix: scope the comparison to the automatic trigger and the non-forced operator path, preserving `force`, or state explicitly that `force` now enforces the watermark (a behavioural change).
- Status: open
- Origin: initial

### SPEC-R1-F09 — [minor] Automatic-path rejection is not observable, and the refill-history wording conflicts

- Location: `specs/costguard/spec.md#L11,L33,L38`; `backend/agents/monitor.py#L327-332`
- Evidence: requirement 1's scenario asserts "the result is `rejected_no_realized_profit`", but `record_usage` discards the gate's return value and only returns `get_status()`. Requirement 2 says a rejection "MUST NOT append a successful refill event" (allowing a rejection event), while its scenario says "no refill event is appended to the refill history" (forbidding any event).
- Required fix: align the two statements and assert an observable state (balance, epoch total, history) or require the automatic path to expose a distinct rejection event in the status.
- Status: open
- Origin: initial

### SPEC-R1-F10 — [minor] Requirement 9 is meta and includes an unobservable mutation assertion

- Location: `specs/costguard/spec.md#L216-236`
- Evidence: requirement 9 mandates a test-suite change and its scenario's THEN "removing the PnL from the automatic path makes that test fail" is a mutation-testing claim, not a runtime outcome. The negative/zero automatic behaviour is already specified in requirements 1–2 and repeated here.
- Required fix: move the mutation check to `tasks.md`/`## Verification` and reduce requirement 9 to the observable assertions, or drop the duplicated behaviour.
- Status: open
- Origin: initial

### SPEC-R1-F11 — [minor] UI missing-watermark scenario offers two acceptable outcomes

- Location: `specs/costguard/spec.md#L188-192`
- Evidence: "the OpenRouter card shows an unavailable marker **or** omits the threshold text" cannot be verified by a single deterministic assertion.
- Required fix: choose one rendering (for example, an em dash) and assert it.
- Status: open
- Origin: initial

### SPEC-R1-F12 — [minor] Missing-PnL failure is not defined as an observable outcome

- Location: `specs/costguard/spec.md#L19-23`; `tasks.md#L3`
- Evidence: "the call fails before mutating any state" does not say whether the failure is a raised exception (missing required argument) or a structured rejection; the test cannot assert both.
- Required fix: state the observable (for example, `TypeError` from the missing required argument) and assert it.
- Status: open
- Origin: initial

### SPEC-R1-F13 — [minor] Hydration cost source and rotated ledger segment are unspecified

- Location: `specs/costguard/spec.md#L142-144`; `backend/agents/monitor.py#L158-162`; `backend/core/transcript_palace.py#L94-117`
- Evidence: "the costs of ledger entries" is ambiguous; the code uses `max(entry cost_usd, computed cost)`. Rotation renames the active file to `.1` at 100 MB, and `hydrate_from_ledger` reads only the active file, so in-window entries can be silently omitted.
- Required fix: state the authoritative cost field and either handle the rotated segment or declare it out of scope.
- Status: open
- Origin: initial

### SPEC-R1-F14 — [minor] Task list does not cover tests that set `total_cost_usd` directly

- Location: `tasks.md#L12,L29`; `backend/tests/test_hierarchy_v3.py#L208`; `backend/tests/test_integrity_provenance.py#L726`
- Evidence: task 2.1 says to replace the cumulative `total_cost_usd` accounting, but two existing tests set that attribute directly to force budget exhaustion. Task 4.4 only mentions the status-label assertion and the watermark comment.
- Required fix: add a task to update those tests to the new window API, or preserve `total_cost_usd` as a derived property.
- Status: open
- Origin: initial

### SPEC-R1-F15 — [nit] Status contract change is described as shape-only

- Location: `proposal.md#L56-60`; `backend/agents/monitor.py#L452-453`
- Evidence: the proposal says the `cost_guard` block "keeps its shape; `auto_wallet_refill` changes value". The value change from `DISABLED_BY_SECURITY_POLICY` to `ENABLED_PROFIT_GATED`/`DISABLED` is a semantic, potentially breaking enum change for external consumers. `auto_refill_policy` already exists in the code; the delta makes it stateful rather than adding it.
- Required fix: state the enum value change as an observable contract change and note that `auto_refill_policy` is pre-existing; document the migration for any external consumer.
- Status: open
- Origin: initial

## Scope-concern rulings

1. **Hydration independent of `REDIS_URL`** — in scope (issue #5 §5 names the Redis-gated hydration and the restart reset) and testable through the ledger-path scenarios, but **not safe as written**: the fixed, non-injectable path makes the suite non-hermetic and can read a 100 MB file synchronously at construction (F04).
2. **Status fields** — coherent. Keeping `auto_wallet_refill` and changing its value, while making the existing `auto_refill_policy` follow the same state, describes the behaviour truthfully. Caveat: the enum value change is a semantic contract change for external consumers, and `auto_refill_policy` is not new (F15).
3. **UI `$15` vs backend `$10`** — **not** an explicit follow-up or non-goal today. The spec single-sources only the low watermark; the button amount remains hardcoded and diverges from `OPENROUTER_REFILL_AMOUNT_USD` (`$10.00`). Minimal fix: add a Non-goals bullet (F05).

## Checks run

- `openspec validate fix-costguard-python-gate --strict` → "Change 'fix-costguard-python-gate' is valid", exit 0.
- `scripts/sdlc/spec-lint.py --change fix-costguard-python-gate` → PASS; Review Card 149 words, 1 diagram, ~1.2 min; warning: 20 unchecked tasks (expected at SPEC).
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` → PASS; warning: no verdicts found (expected for R1).
- Independent checks: 9 requirements / 34 scenarios counted; no duplicate requirement or scenario names; no `TBD`/`TODO`/`???`; `grep -rn "max(125.0" backend/` → no output (post-#7 preserved); `grep -n "?? 5.0" frontend/src/components/MasterOverview.jsx` → line 401 still present (expected to be fixed by task 3.2).
- Review Card read time: 1.2 min, within the 5.0 min budget.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-costguard-python-gate",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "2dea6d4f046fa32eb53b0191cf1c790473bac22f",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The intent is sound and all automated checks pass, but four majors block approval: money-path lane right-sizing (S vs L), an ADR-0003 watermark contradiction, an undefined automatic-path store wiring, and non-hermetic construction-time hydration from the dev ledger.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": ".sdlc/fix-costguard-python-gate/state.json#L6; sdlc/PROTOCOL.md#L54-62; openspec/config.yaml#L19-20",
      "evidence": "state.json records lane S (reason: backend-only CostGuard slice, 4-7 files). PROTOCOL §2.1 assigns Lane L to any money/risk path; config.yaml lists CostGuard daily cap and no unbounded refills under capital protection. The delta changes the refill gate and daily-spend accounting.",
      "required_fix": "Upgrade to Lane L (autonomous per PROTOCOL §2.1), record lane_change, add design.md, and route through PLAN review; or record a written human-approved Lane S exception."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L167-169; proposal.md#L10; docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30",
      "evidence": "ADR-0003 (Accepted) states low_watermark_usd = $5.00; the delta mandates a $2.00 default; the Review Card says Decision needed: None. The ADR's gate also lists kill-switch inactive, absent from the delta's three caps and not named as a specific non-goal.",
      "required_fix": "Reconcile the watermark explicitly (amend ADR-0003 to $2.00 with rationale, or adopt $5.00) and add the ADR to Impact; state the kill-switch condition as a requirement or an explicit non-goal."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L5; backend/agents/monitor.py#L66,L75-119,L295-332; backend/agents/orchestrator.py#L43; backend/tests/test_integrity_provenance.py#L723,L810",
      "evidence": "LLMMonitorAgent holds no store; record_usage fires the automatic refill; OrchestratorAgent constructs it with only name. Tests inject a per-test HybridStateStore into the orchestrator, so reading the module-global state_store would evaluate the wrong PnL. The spec defines neither the store instance, the injection mechanism, nor the no-store failure path.",
      "required_fix": "Specify that the orchestrator injects its own store (constructor argument or callable) and that the automatic path calls that instance's measured_realized_pnl_usd(); add a scenario where no measured source exists and no refill occurs."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L142-144; backend/agents/monitor.py#L118-128; backend/tests/test_architecture.py#L28-34; backend/tests/test_hierarchy_v3.py#L22-25; backend/core/transcript_palace.py#L95,L115",
      "evidence": "Hydration is mandated from the fixed backend/data/transcript_ledger.jsonl on every construction regardless of REDIS_URL. The file is gitignored and dev-local. test_architecture asserts budget_exhausted false at startup without isolating the path; test_hierarchy_v3 patches transcript_palace.storage_path, which hydration does not use. The ledger can reach 100 MB and is read synchronously.",
      "required_fix": "Make the ledger path injectable at construction (or via an env override) with the current path as default, and require tests to pass an isolated temp path; add a scenario that an existing dev ledger does not change the suite's initial spend and state the construction read-cost bound."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "frontend/src/components/MasterOverview.jsx#L205; backend/agents/monitor.py#L108-110; proposal.md#L48-54",
      "evidence": "The UI posts amount_usd 15.0 while OPENROUTER_REFILL_AMOUNT_USD defaults to 10.00. The Non-goals do not mention the refill amount, so the boundary around it is undefined.",
      "required_fix": "Add an explicit Non-goals bullet (follow-up on issue #5), or render openrouter_credit.refill_amount_usd and use it for the button label and payload."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L44-46; openspec/specs/integrity/spec.md#L264-266; specs/costguard/spec.md#L5,L13-17",
      "evidence": "The proposal claims no existing spec defines CostGuard behaviour, but integrity#L264-266 defines the refill-caller measured-PnL rule and defers the remaining CostGuard defects. The new costguard delta restates the operator-path rule without a MODIFIED declaration.",
      "required_fix": "Reference the integrity requirement and either scope costguard to the remaining defects or add a MODIFIED delta that copies the full integrity requirement block."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L61,L77; backend/agents/monitor.py#L111-113",
      "evidence": "The delta hardcodes the epoch cap at $25.00; the code resolves OPENROUTER_MAX_EPOCH_REFILL_USD (default 25.00). The fixed single-refill bound (0, $25.00] is a different constraint.",
      "required_fix": "State the epoch cap as the configured value (OPENROUTER_MAX_EPOCH_REFILL_USD, default $25.00) and keep the fixed single-refill bound distinct."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L169; backend/agents/monitor.py#L382-387; frontend/src/components/MasterOverview.jsx#L205",
      "evidence": "The operator button sends force true, and the gate skips the watermark when force is set. A literal reading of every refill trigger MUST compare the balance against the watermark would refuse on-demand recharges above it.",
      "required_fix": "Scope the comparison to the automatic trigger and the non-forced operator path, preserving force, or state explicitly that force now enforces the watermark."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L11,L33,L38; backend/agents/monitor.py#L327-332",
      "evidence": "record_usage discards the gate's return, so the asserted rejected_no_realized_profit result is not observable. Requirement 2 allows a rejection event while its scenario forbids any refill-history event.",
      "required_fix": "Align the wording and assert observable state (balance, epoch total, history), or require a distinct rejection event exposed in status."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L216-236",
      "evidence": "Requirement 9 mandates a test and its scenario THEN removing the PnL from the automatic path makes that test fail is a mutation claim, not a runtime outcome; the negative/zero behaviour is already specified in requirements 1-2.",
      "required_fix": "Move the mutation check to tasks.md/Verification and reduce requirement 9 to the observable assertions, or drop the duplication."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L188-192",
      "evidence": "The missing-watermark scenario allows an unavailable marker or omitting the threshold text, two outcomes a single deterministic assertion cannot verify.",
      "required_fix": "Choose one rendering (for example, an em dash) and assert it."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L19-23; tasks.md#L3",
      "evidence": "The missing-PnL call must fail before mutating state, but the spec does not say whether the failure is a raised exception or a structured rejection; the test cannot assert both.",
      "required_fix": "State the observable (for example, TypeError from the missing required argument) and assert it."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "specs/costguard/spec.md#L142-144; backend/agents/monitor.py#L158-162; backend/core/transcript_palace.py#L94-117",
      "evidence": "The costs of ledger entries is ambiguous; the code uses max(entry cost_usd, computed cost). Rotation renames the active file to .1 at 100 MB and hydration reads only the active file, so in-window entries can be omitted.",
      "required_fix": "State the authoritative cost field and either handle the rotated segment or declare it out of scope."
    },
    {
      "id": "SPEC-R1-F14",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L12,L29; backend/tests/test_hierarchy_v3.py#L208; backend/tests/test_integrity_provenance.py#L726",
      "evidence": "Task 2.1 replaces cumulative total_cost_usd accounting, but two existing tests set that attribute directly to force budget exhaustion; task 4.4 only mentions the status label and watermark comment.",
      "required_fix": "Add a task to update those tests to the new window API, or preserve total_cost_usd as a derived property."
    },
    {
      "id": "SPEC-R1-F15",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L56-60; backend/agents/monitor.py#L452-453",
      "evidence": "The proposal describes the status contract as shape-only, but auto_wallet_refill changes enum value, which is a semantic and potentially breaking change for external consumers. auto_refill_policy already exists; the delta makes it stateful rather than adding it.",
      "required_fix": "State the enum value change as an observable contract change, note that auto_refill_policy is pre-existing, and document the migration for any external consumer."
    }
  ],
  "closed": []
}
```
