stage: spec
round: 1
head_sha: 2dea6d4f046fa32eb53b0191cf1c790473bac22f
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: >-
      Coordinator upgraded the change to Lane L; `.sdlc/fix-costguard-python-gate/state.json`
      now records `"lane": "L"` with a `lane_change` from S to L and the issue carries the
      lane-L label. Per the coordinator's R1 instruction, this round authors the SPEC only;
      `design.md` and the Lane L `tasks.md` are the PLAN stage's artifacts.
  - id: SPEC-R1-F02
    action: fixed
    evidence: >-
      Chose `$2.00` (more conservative). The Review Card now states
      "Decision needed: Approve the ADR-0003 amendment: low watermark `$5.00` → `$2.00`,
      and the ADR's kill-switch condition enforced by the Python gate." `proposal.md`
      What Changes and Impact list the ADR-0003 amendment as a deliverable. The new
      requirement "Refills are refused while the kill switch is active" adds the ADR's
      fourth condition with three scenarios (automatic, forced operator, inactive).
  - id: SPEC-R1-F03
    action: fixed
    evidence: >-
      New requirement "The CostGuard receives its measured PnL source by injection" specifies
      `LLMMonitorAgent` accepting a store source at construction (default none), the
      orchestrator injecting its own per-test store, no module-global source, and a fail-closed
      `rejected_no_pnl_source` operator path. Four scenarios cover injected-store precedence,
      automatic no-refill without a source, operator rejection without a source, and
      construction without a store.
  - id: SPEC-R1-F04
    action: fixed
    evidence: >-
      Requirement "Ledger hydration is injectable, lazy, and bounded" now specifies an
      injectable ledger path with `COSTGUARD_LEDGER_PATH` override and a module-anchored
      production default, zero ledger reads at construction (lazy hydration on first spend
      access or explicit call), streaming of the active file plus the most recent rotated
      segment, no whole-file buffering, and an isolated ledger path required in tests.
      Scenarios cover zero construction reads, a developer ledger isolated from the suite,
      CWD independence, the rotated segment, and the missing-file path.
  - id: SPEC-R1-F05
    action: fixed
    evidence: >-
      Added an explicit Non-goals bullet: "Aligning the UI's fixed `$15.00` refill button with
      `OPENROUTER_REFILL_AMOUNT_USD` (`$10.00`); tracked as a follow-up on issue #5."
  - id: SPEC-R1-F06
    action: fixed
    evidence: >-
      `proposal.md` now lists `integrity` as a Modified Capability and explains that the
      requirement "Refill gating consumes null-safe measured PnL only" keeps its caller rules
      while its out-of-scope sentence changes. Added `specs/integrity/spec.md` with a
      `## MODIFIED Requirements` block copying the full canonical requirement and all four
      scenarios, with the scope sentence updated to point the automatic path, rolling window,
      low-watermark constants, and injection at the `costguard` capability.
  - id: SPEC-R1-F07
    action: fixed
    evidence: >-
      Requirement "Profit-share and epoch caps apply on every path" now resolves the epoch cap
      from `OPENROUTER_MAX_EPOCH_REFILL_USD` (default `$25.00`) and keeps the fixed
      single-refill bound `(0, $25.00]` explicitly distinct. Scenarios cover the default cap
      rejecting `$23.00 + $4.00` and a configured `$40.00` cap allowing the same refill.
  - id: SPEC-R1-F08
    action: fixed
    evidence: >-
      New requirement "Force bypasses only the low-watermark check" states that `force` only
      skips the balance-versus-watermark comparison and does not bypass the PnL gate,
      profit-share cap, single-refill bound, epoch cap, or kill-switch check. The watermark
      requirement now scopes the comparison to the automatic trigger and the non-forced
      operator path. Three scenarios cover the permitted forced refill and the two forbidden
      bypasses.
  - id: SPEC-R1-F09
    action: fixed
    evidence: >-
      Automatic-path scenarios now assert observable state only: unchanged credit balance,
      unchanged epoch refilled total, and no event appended to the refill history. Removed the
      unobservable claim that `record_usage` returns `rejected_no_realized_profit`; only the
      operator path asserts a returned status. The rejection wording consistently forbids any
      refill-history append.
  - id: SPEC-R1-F10
    action: fixed
    evidence: >-
      Removed the meta requirement "The automatic profit gate is regression-tested" and its
      mutation-testing claim. The runtime negative/zero/positive automatic behaviour remains
      specified in "A refill requires strictly positive realized profit" and "Profit-share and
      epoch caps apply on every path". The mutation check and test tasks are deferred to the
      PLAN stage because `tasks.md` is PLAN-owned in Lane L.
  - id: SPEC-R1-F11
    action: fixed
    evidence: >-
      The missing-watermark scenario now has one deterministic outcome: "the OpenRouter card
      displays `—` for the threshold" and no numeric threshold. The requirement text mandates
      the em dash.
  - id: SPEC-R1-F12
    action: fixed
    evidence: >-
      Requirement "Every refill path requires a measured realized PnL" now states that a call
      omitting the value raises `TypeError` before any state mutation. The scenario asserts the
      `TypeError` and unchanged balance, epoch total, and history.
  - id: SPEC-R1-F13
    action: fixed
    evidence: >-
      Hydration now states the authoritative per-entry cost as
      `max(entry cost_usd, computed cost from model and token counts)`, with a scenario where a
      recorded `$0.01` is superseded by a computed `$1.00`. The most recent rotated segment
      `<name>.1` is read and has a scenario proving an in-window entry in that segment
      contributes. Segments older than `<name>.1` are an explicit Non-goal.
  - id: SPEC-R1-F14
    action: fixed
    evidence: >-
      Requirement "Daily spend is a rolling 24-hour window" now specifies `total_cost_usd` as
      the derived window total and not independently assignable, with a scenario asserting the
      value reflects the window (`$1.00`) rather than lifetime spend (`$5.00`). The test
      migrations that currently assign the aggregate directly are therefore dev work under the
      PLAN-owned `tasks.md`; this SPEC round does not write that file.
  - id: SPEC-R1-F15
    action: fixed
    evidence: >-
      `proposal.md` What Changes marks the `auto_wallet_refill` enum change as
      "**BREAKING (status value)**" and states that `auto_refill_policy` is pre-existing. Impact
      documents the migration for external consumers: accept `ENABLED_PROFIT_GATED` and
      `DISABLED`, and read `auto_refill_policy` for the policy state.
