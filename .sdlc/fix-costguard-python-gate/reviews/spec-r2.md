# SPEC Review — Round 2

## Summary

APPROVE. All 15 R1 findings are closed at `1ef4c63`. The change is Lane L with PLAN pending; the ADR-0003 `$2.00` amendment is a declared deliverable and the kill-switch condition is a requirement; store injection with fail-closed `rejected_no_pnl_source` is specified; hydration is injectable, lazy, module-anchored, streaming, and bounded with an isolated test path. The integrity MODIFIED delta copies the merged #7 requirement verbatim — exact header, all four scenarios — changing only the scope sentence. The `$15`/`$10` non-goal, configurable epoch cap, force semantics, observable automatic assertions, dropped meta requirement, `TypeError`, cost derivation, derived `total_cost_usd`, and breaking status migration are closed. `openspec validate`, `spec-lint`, and `sdlc.sh check` pass. Remaining items are non-blocking PLAN/conductor follow-ups.

## Findings

### SPEC-R1-F01 — [major] Change is a money/capital-protection path but is authored as Lane S

- Location: `.sdlc/fix-costguard-python-gate/state.json#L6,L8,L33-34`; issue #5 lane-upgrade comment and latest `sdlc:state` block
- Evidence: `state.json` now records `"lane": "L"` and a `lane_change` from S to L citing the capital-protection path; the PLAN stage is `pending`, and the issue logbook carries an explicit "Lane upgrade S → L (autonomous)" comment plus a `lane: L` state block. `spec-lint` correctly warns that `design.md` is a PLAN-stage artifact.
- Required fix: (R1) upgrade to Lane L, record `lane_change`, add `design.md`, route through PLAN review.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] Low-watermark default contradicts accepted ADR-0003 and is declared decision-free

- Location: `openspec/changes/fix-costguard-python-gate/proposal.md#L10,L37,L65`; `specs/costguard/spec.md#L157-177`; `docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L30`
- Evidence: the Review Card's decision field now reads "Approve the ADR-0003 amendment: low watermark `$5.00` → `$2.00`, and the ADR's kill-switch condition enforced by the Python gate." `proposal.md` What Changes declares the amendment a deliverable, Impact lists the ADR, and the new requirement "Refills are refused while the kill switch is active" (`spec.md#L157`) plus its three scenarios covers the ADR's fourth condition. ADR-0003#L30 still says `$5.00`; the amendment is correctly DEV work, not SPEC work.
- Required fix: (R1) reconcile explicitly and state the kill-switch condition.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] Automatic path cannot reach "the state store's" measured PnL as specified

- Location: `specs/costguard/spec.md#L3-29`; `backend/agents/orchestrator.py#L43`; `backend/core/state_store.py#L91,L883`; `backend/server.py#L262`
- Evidence: the new requirement "The CostGuard receives its measured PnL source by injection" mandates a constructor source defaulting to none, forbids a module-global source, requires `OrchestratorAgent` to inject its own (including per-test) store, and requires `measured_realized_pnl_usd()` on that instance. Four scenarios cover injected-store precedence, automatic no-refill, operator `rejected_no_pnl_source`, and store-less construction. The store already exposes `measured_realized_pnl_usd()` and `kill_switch_active`; `proposal.md#L63` lists the orchestrator and server wiring in Impact.
- Required fix: (R1) define the store instance, injection mechanism, and no-source failure path.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] Construction-time hydration from the fixed dev ledger is non-hermetic and unbounded

- Location: `specs/costguard/spec.md#L218-262`
- Evidence: "Ledger hydration is injectable, lazy, and bounded" now requires an injectable constructor path, `COSTGUARD_LEDGER_PATH`, a module-anchored production default (never the CWD), zero ledger reads at construction, lazy hydration on first daily-spend access or explicit call, streaming of the active file plus `<name>.1`, no whole-file buffering, and an isolated test-suite path. Scenarios assert zero construction reads, an isolated ledger blocking a developer ledger, CWD independence, the rotated segment, and the missing-file path.
- Required fix: (R1) make the path injectable, require an isolated test path, add the hermeticity scenario, and bound the read cost.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [minor] UI refill button `$15` vs backend `$10` is neither in scope nor an explicit non-goal

- Location: `proposal.md#L57`
- Evidence: Non-goals now carries "Aligning the UI's fixed `$15.00` refill button with `OPENROUTER_REFILL_AMOUNT_USD` (`$10.00`); tracked as a follow-up on issue #5."
- Required fix: (R1) add an explicit Non-goals bullet or single-source the refill amount.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [minor] Proposal wrongly claims no existing spec defines CostGuard behaviour

- Location: `proposal.md#L50`; `specs/integrity/spec.md#L1-29`
- Evidence: the proposal now lists `integrity` under Modified Capabilities with the explanation that the requirement keeps its caller rules while its out-of-scope sentence changes, and the `integrity` delta exists with a `## MODIFIED Requirements` block. The block copies the full canonical requirement verbatim (see the integrity check below).
- Required fix: (R1) reference the integrity requirement and add a full MODIFIED delta.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [minor] Epoch cap hardcoded to `$25.00` although it is configured

- Location: `specs/costguard/spec.md#L83,L97-107`
- Evidence: the requirement resolves the epoch cap from `OPENROUTER_MAX_EPOCH_REFILL_USD` with a `$25.00` default and keeps the fixed `(0, $25.00]` single-refill bound distinct. Scenarios cover the default cap rejecting `$23.00 + $4.00` and a configured `$40.00` cap allowing it.
- Required fix: (R1) separate the configured epoch cap from the fixed single-refill bound.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [minor] "Every refill trigger MUST compare" collides with operator `force`

- Location: `specs/costguard/spec.md#L137-155,L266`
- Evidence: the new requirement "Force bypasses only the low-watermark check" states that `force` skips only the balance-versus-watermark comparison and must not bypass the PnL gate, profit-share cap, single-refill bound, epoch cap, or kill switch. The watermark requirement scopes the comparison to the automatic trigger and the non-forced operator path. Three scenarios cover the permitted forced refill and two forbidden bypasses.
- Required fix: (R1) scope the comparison and preserve `force`.
- Status: closed
- Origin: initial

### SPEC-R1-F09 — [minor] Automatic-path rejection is not observable, and the refill-history wording conflicts

- Location: `specs/costguard/spec.md#L55,L57-67,L307-312`
- Evidence: automatic-path scenarios assert only observable state — unchanged balance, unchanged epoch refilled total, and no event appended to refill history. The unobservable `record_usage` return claim is gone; only the operator path asserts `rejected_no_realized_profit`. The requirement and scenarios now consistently forbid any refill-history append on rejection.
- Required fix: (R1) align the wording and assert observable state.
- Status: closed
- Origin: initial

### SPEC-R1-F10 — [minor] Requirement 9 is meta and includes an unobservable mutation assertion

- Location: `specs/costguard/spec.md` (requirement set); `specs/costguard/spec.md#L53-79`
- Evidence: the former "The automatic profit gate is regression-tested" requirement and its mutation-testing scenario are removed; the new spec has no "regression-tested" requirement. Negative/zero/positive automatic behaviour remains specified under "A refill requires strictly positive realized profit" and the caps requirement. The mutation check is a PLAN/verification task.
- Required fix: (R1) drop the meta requirement and keep only observable assertions.
- Status: closed
- Origin: initial

### SPEC-R1-F11 — [minor] UI missing-watermark scenario offers two acceptable outcomes

- Location: `specs/costguard/spec.md#L266,L285-289`
- Evidence: the requirement mandates the em dash and the scenario has one deterministic outcome: the OpenRouter card displays `—` for the threshold and no numeric threshold.
- Required fix: (R1) choose one rendering and assert it.
- Status: closed
- Origin: initial

### SPEC-R1-F12 — [minor] Missing-PnL failure is not defined as an observable outcome

- Location: `specs/costguard/spec.md#L33,L35-39`
- Evidence: the requirement now says a call omitting the realized trading PnL raises `TypeError` before any state mutation; the scenario asserts the `TypeError` and unchanged balance, epoch total, and history.
- Required fix: (R1) state the observable failure and assert it.
- Status: closed
- Origin: initial

### SPEC-R1-F13 — [minor] Hydration cost source and rotated ledger segment are unspecified

- Location: `specs/costguard/spec.md#L220,L238-246`; `proposal.md#L58`
- Evidence: the requirement states the authoritative per-entry cost is `max(entry cost_usd, computed cost from model and token counts)` and reads the most recent rotated segment `<name>.1`. Scenarios prove a recorded `$0.01` is superseded by a computed `$1.00` and that an in-window entry in `<name>.1` contributes. Older segments are an explicit Non-goal.
- Required fix: (R1) state the authoritative cost and handle or scope the rotated segment.
- Status: closed
- Origin: initial

### SPEC-R1-F14 — [minor] Task list does not cover tests that set `total_cost_usd` directly

- Location: `specs/costguard/spec.md#L181,L212-216`; `backend/tests/test_integrity_provenance.py#L726`; `backend/tests/test_hierarchy_v3.py#L208`
- Evidence: the requirement defines `total_cost_usd` as the derived rolling-window total and says it must not be independently assignable, with a scenario distinguishing `$1.00` window spend from `$5.00` lifetime spend. The two existing tests that assign the aggregate directly must migrate under the PLAN-owned `tasks.md`.
- Required fix: (R1) add a migration task or preserve `total_cost_usd` as a derived property; the latter is now specified.
- Status: closed
- Origin: initial

### SPEC-R1-F15 — [nit] Status contract change is described as shape-only

- Location: `proposal.md#L39,L66`; `specs/costguard/spec.md#L291-293`
- Evidence: What Changes marks the `auto_wallet_refill` enum change as "**BREAKING (status value)**" and notes `auto_refill_policy` is pre-existing; Impact states the migration for external consumers (accept `ENABLED_PROFIT_GATED`/`DISABLED`, read `auto_refill_policy` for policy state). The status requirement fixes both labels for enabled and disabled states.
- Required fix: (R1) describe the enum change as an observable contract change and document the migration.
- Status: closed
- Origin: initial

## Integrity MODIFIED-delta check (critical)

- **Header**: `specs/integrity/spec.md#L1` is exactly `## MODIFIED Requirements`; `#L3` is exactly `### Requirement: Refill gating consumes null-safe measured PnL only`, matching `openspec/specs/integrity/spec.md#L264`.
- **Completeness**: a line-level diff of the canonical block against the delta block shows the requirement body copied in full and all four scenarios (`#L7,L13,L18,L24`) byte-identical; the only textual change is the final scope sentence (automatic path, rolling window, low-watermark constants, and injection now deferred to `costguard`; Rust validator, `/credits` source, and Rust routing kept out of scope). A trailing blank line differs; no semantic drift.
- **No contradiction**: the canonical normative sentences (sum only non-null `MEASURED` leaf PnL, no simulated `paper_model` PnL, no `max(125.0, …)` floor) are preserved verbatim. `openspec validate --strict` accepts the delta.

## Checks run

- `openspec validate fix-costguard-python-gate --strict` → "Change 'fix-costguard-python-gate' is valid", exit 0.
- `scripts/sdlc/spec-lint.py --change fix-costguard-python-gate` → PASS; Review Card 172 words, 1 diagram, ~1.4 min. Warnings: `design.md` absent (PLAN stage), 20 unchecked tasks (expected at SPEC).
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` → PASS (OpenSpec + spec-lint + verdict-lint; R1 verdict recognized).
- Independent: 11 requirements / 46 scenarios in `costguard`; 1 requirement / 4 scenarios in `integrity`; no duplicate requirement or scenario names; no `TBD`/`TODO`/`???`; `grep -rn "max(125.0" backend/` → no output.
- Review Card read time: 1.4 min (spec-lint), within the 5.0 min budget.

## Follow-ups (non-blocking)

1. **PLAN-owned `tasks.md` is the stale Lane S list.** It contradicts the approved spec: task 2.5 still mandates hydration at initialization (spec: zero construction reads, `costguard#L220-226`); task 1.5 fixed the epoch cap at `$25.00` (spec: configurable, `#L83`); task 3.2 says "non-numeric unavailable marker" (spec: em dash, `#L266`); task 4.4 omits the two `total_cost_usd` assignments (`test_integrity_provenance.py#L726`, `test_hierarchy_v3.py#L208`), the isolated ledger path, and the mutation check. PLAN must rewrite it.
2. **`state.json#L7` `lane_reason` still carries the Lane S rationale** ("Backend-only CostGuard slice; 4-7 files...") despite `lane: L`; update it to the capital-protection rationale.
3. **Issue #5 labels are incomplete.** `gh issue view 5 --json labels` returns only `bug`; PROTOCOL §10.1 expects `sdlc`, `sdlc:lane-l`, and a stage label. The revision note's claim that "the issue carries the lane-L label" is not borne out, though the issue's state block and lane-upgrade comment do record Lane L.
4. **Status label in the no-source state.** `costguard#L293` mandates `ENABLED_PROFIT_GATED` whenever `auto_refill_enabled` is true, including a store-less `CostGuard` that fails closed; add a clarification/scenario so "truthful status" and the fail-closed state cannot be read as contradictory.
5. **Lazy-hydration ordering.** "First daily-spend access" hydration plus "replace the window" (`#L220`) can drop in-memory usage recorded before an explicit re-hydration; define hydration-before-record or add a scenario asserting recorded usage survives explicit hydration.
6. Several gate scenarios state amounts without the balance/PnL preconditions needed to reach the asserted branch (e.g. `#L91-95`, `#L97-101`, `#L109-113`); tests must supply them.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-costguard-python-gate",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "1ef4c638295fbc8e3fc24601d68b7c1250c2e735",
  "verdict": "APPROVE",
  "summary": "All 15 R1 findings are closed at 1ef4c63, the integrity MODIFIED delta faithfully copies the merged #7 requirement block, and all required checks pass; no open blocker or major remains.",
  "findings": [],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08",
    "SPEC-R1-F09",
    "SPEC-R1-F10",
    "SPEC-R1-F11",
    "SPEC-R1-F12",
    "SPEC-R1-F13",
    "SPEC-R1-F14",
    "SPEC-R1-F15"
  ]
}
```
