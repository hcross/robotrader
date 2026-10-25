# PLAN Review — Round 2 (closure)

## Summary

**APPROVE** at `2f57e0f`. All ten R1 findings are closed; zero blocker, major, minor, or nit remain open, and no new finding qualifies under the R2 rules. The revision restores the working CI discovery form (`working-directory: backend`, `PYTHONPATH=..`, `-s tests`), declares the `trading.py` `commit` parameter with both behaviours tested, and replaces the false budget-helper claims with a `float64` + `le 0` + `fail` guard whose negative and non-numeric cases I reproduced under Helm v4.2.3. The stale-lock check is hermetic and its fail-closed result reproduced; the `litellm` residual is explicitly documented; the resolver/error boundary, verification commands, child-state ordering, Helm pin, and observability note are all in place. The approved spec is byte-identical. Non-blocking follow-up for DEV: D8/R4/task 3.1 say an explicit zero fails, but Sprig `empty 0` renders `5.0`; that fallback is safe and outside the spec's empty-string scenario — correct the wording, do not change behaviour.

## Checklist walk (sdlc/checklists/plan.md)

| Section | Result | Evidence |
|---|---|---|
| 1. Traceability | PASS | 11 requirements and 38 scenarios map to tasks 1.1–7.1; the spec hash is unchanged from `2a7f035` (`ac36671a…`); no task adds unapproved behaviour. |
| 2. Decisions | PASS | D1–D16 name alternatives and technical rejections; D6/D11 flag the one-way doors; no new dependency. D8's zero wording is a non-blocking follow-up (below). |
| 3. Contracts and data | PASS / N/A | The 503 error contract is defined once; success paths, `PolicyEnvelope`, Redis IPC, DB, and chain/venue boundaries are untouched. |
| 4. Hot path and performance | PASS / N/A | No `StrategyPod`, `HardRiskGate`, or backtest/paper/live logic change; the resolver is a two-path `exists()` check; the removed compiler fallback eliminates the blocking request-path build. |
| 5. Safety and security | PASS | Kill switch stays eager and fail-safe (D6); `/policy/regime` commits only after a successful backtest; no secrets in the 503 detail; invalid Helm budget values fail closed or fall back to `5.0`. |
| 6. Test strategy | PASS | Resolver precedence, no-compiler, both-methods, handler shape, and subprocess endpoint matrix are planned; child state is reset and `/risk/kill` runs last; negative Helm and stale-lock checks exist. |
| 7. Rollout and rollback | PASS | Ordered migration (image then chart), concrete rollback (digest/helm rollback, code revert, dependency restore), and an observability/cost note. |
| 8. Tasks | PASS | 24 checkboxes in 7 dependency-ordered groups; every task names its coverage; `## Verification` is root-runnable with explicit assertions. |

## Findings (all closed; most severe first)

### PLAN-R1-F01 — [major] CI discovery command is invalid under `poetry -C backend` — **closed**
- Location: `tasks.md#L38`; `design.md#L110,L208-L211`; `tasks.md#L260-L261`
- Evidence: Task 5.1 now keeps `working-directory: backend` with `PYTHONPATH=.. poetry run python -m unittest discover -s tests -v` and states the Rust build runs from the repository root with `--manifest-path engine-rs/Cargo.toml`. I re-verified that `poetry -C backend run python -c "import os; print(os.getcwd())"` prints `.../backend` (Poetry 2.5.1), so the rejected form is explicitly documented. The CI wiring block greps both accepted forms.
- Required fix: Use the existing working-directory form or state the corrected `PYTHONPATH`/`-s` values; state the build step's root working directory.
- Status: closed
- Origin: initial

### PLAN-R1-F02 — [major] Task 1.4 requires an undeclared `backend/agents/trading.py` change — **closed**
- Location: `design.md#L102,L115-L120`; `tasks.md#L12-L13`; `backend/agents/trading.py#L30`; `backend/server.py#L324`
- Evidence: D5 now specifies `MetaAllocatorAgent.apply_regime_preset(preset, commit: bool = True)` in `backend/agents/trading.py`, with the default preserving eager `SET_REGIME`/chat commits and `/api/v1/policy/regime` passing `commit=False` then committing after the backtest. The footprint note names `trading.py`; task 1.4 is executable; task 1.5 adds the both-behaviours test. I confirmed the current signature at `trading.py#L30` and the route caller at `server.py#L324`; the `SET_REGIME` path (`trading.py#L25`) keeps the default.
- Required fix: Add `trading.py` to the footprint and task 1.4 (`commit: bool = True` or equivalent builder), preserve eager `SET_REGIME`/chat commits, and test both behaviours.
- Status: closed
- Origin: initial

### PLAN-R1-F03 — [major] Budget helper claims are false for non-numeric and negative values — **closed**
- Location: `design.md#L105,L155-L160`; `tasks.md#L23,L131-L139`
- Evidence: D8 and R4 now define absent/empty → `5.0`; otherwise `float64` + `le 0` + `fail`; valid values → `printf "%.1f"`. I built the described helper on Helm v4.2.3: absent → `"5.0"`, empty override → `"5.0"`, `7.5` → `"7.5"`, `--set …=-1` and `--set-string …=abc` both exit non-zero with the actionable `fail` message and no `%!f(...)`. The negative and non-numeric assertions are now in tasks 3.1/5.3 and the Verification block. Residual (non-blocking, follow-up): `empty 0` is true in Go templates, so an explicit `0` renders `5.0` rather than failing; the value is still a valid positive budget, outside the spec's empty-string scenario. Correct D8/R4/task 3.1 wording during DEV.
- Required fix: Make D8 and R4 agree and validate or narrow the invalid-value claims; add negative/non-numeric render assertions.
- Status: closed
- Origin: initial

### PLAN-R1-F04 — [minor] Stale-lock negative check is not hermetic — **closed**
- Location: `tasks.md#L178-L199`
- Evidence: The check now uses `backup="$(mktemp)"`, an `EXIT` trap that restores and removes the backup, a clean-tree precondition and post-check, and an inverted `if cargo build … --locked; then exit 1; fi`. It also states why the local run is an equivalent proxy for the builder stage. I executed the block at this SHA: the locked build failed with `error: cannot update the lock file … because --locked was passed`, the post-check printed `TREE_CLEAN_AFTER`, and `git status --porcelain -- engine-rs/crates/node/Cargo.toml` was empty.
- Required fix: Use `mktemp` + `EXIT` trap, assert a clean tree, and justify the local proxy or run through Docker.
- Status: closed
- Origin: initial

### PLAN-R1-F05 — [minor] `litellm` residual in `strands-agents` extras vs the spec's literal wording — **closed**
- Location: `design.md#L171-L181`; `tasks.md#L45,L211-L215`; `specs/build-packaging/spec.md#L250-L254`
- Evidence: R8 and task 6.1 now state the residual explicitly: the regenerated lock has no `[[package]] name = "litellm"` block, while `strands-agents`'s `[package.extras]` metadata may still name `litellm`; that is copied metadata, not a resolved dependency. The gate remains the package-block grep plus no `litellm` in `pyproject.toml` plus a clean `poetry check --lock`. I confirmed the current lock contains both the package block (`poetry.lock#L1628`) and the extras label (`#L3176`), so the residual is real and pre-existing. **Ruling:** this satisfies the approved scenario under the dependency-declaration reading: requirement 11 mandates retaining `strands-agents`, so a literal string-absence reading is unsatisfiable, and the plan does not narrow the spec silently — it records the residual. No `spec-gap` escalation is required.
- Required fix: Keep the package-block gate and state the residual explicitly; escalate only if the scenario is meant as literal string absence.
- Status: closed
- Origin: initial

### PLAN-R1-F06 — [minor] `backend/core/errors.py` contradicts the web-free state-store rationale — **closed**
- Location: `design.md#L101`; `tasks.md#L11`
- Evidence: D4 now puts only the pure `RustBinaryNotFoundError` in `backend/core/errors.py` and lazy-imports `JSONResponse` inside the handler; task 1.3 states the lazy import and its purpose. `state_store.py` imports only the exception, so no module-level FastAPI dependency enters the resolver path. The D3/D4 rationale is aligned.
- Required fix: Split the pure exception from the FastAPI handler or lazy-import the web dependency; otherwise correct the rationale.
- Status: closed
- Origin: initial

### PLAN-R1-F07 — [minor] Several spec scenarios lack an explicit verification command or assertion — **closed**
- Location: `tasks.md#L58-L277`
- Evidence: The Verification section now asserts the default env set (`OPENROUTER_API_KEY`, `SOLANA_RPC_URL`, `REDIS_URL`, positive `MAX_DAILY_LLM_BUDGET_USD`) and no Ingress; `! grep -qx 'engine-rs/Cargo.lock' .dockerignore` plus Dockerfile copy/locked/release greps; README/AGENTS build-step greps; the no-compiler and both-methods assertions in `test_missing_binary`; CI job/path-filter presence greps; and `gh issue view 9` / `gh pr view` follow-up greps with a documented deferral rule. Each previously unnamed scenario now has a command or an explicit named assertion.
- Required fix: Add explicit commands/assertions or name the evidence source for each scenario.
- Status: closed
- Origin: initial

### PLAN-R1-F08 — [minor] Subprocess 503 test starts live workers and shares mutable store state — **closed**
- Location: `design.md#L111`; `tasks.md#L13`
- Evidence: D14 and task 1.5 specify that the child resets `kill_switch_active` and the policy before each case, runs `/risk/kill` last, and tolerates daemon workers because the child exits after its assertions; the parent asserts `backend.server` is not in `sys.modules`. I confirmed the only existing `backend.server` references in `backend/tests` are the string assertions in `test_health.py`, so the parent-suite invariant is achievable.
- Required fix: Specify child state reset/order and the parent's `sys.modules` assertion.
- Status: closed
- Origin: initial

### PLAN-R1-F09 — [nit] Helm 3.16+ compatibility claimed but unverified — **closed**
- Location: `design.md#L36-L38`; `tasks.md#L40,L258`
- Evidence: The Context drops the untested claim and states only that Helm v4.2.3 is the pinned verification tool, the chart stays `apiVersion: v2`, and a Helm 3-only cluster is unaffected because rendering is client-side; it explicitly says "No Helm 3.x render is claimed". `grep -rn '3\.16'` over the change directory returns no match; the v4.2.3 pin remains in D13, task 5.3, and the CI wiring grep.
- Required fix: Add a Helm 3.x render check or drop the claim; keep the v4.2.3 pin.
- Status: closed
- Origin: initial

### PLAN-R1-F10 — [nit] No observability or cost-impact statement — **closed**
- Location: `design.md#L192-L201`
- Evidence: A new "Observability and cost" subsection states that a missing binary surfaces as a 503 in the access log with the actionable detail, no new metric/alert is added, `/api/v1/health` remains the liveness signal, CI gains one Helm job plus a cached debug Rust build, and removing `litellm` shrinks the dependency graph and image install step with no runtime LLM-spend change.
- Required fix: Add a short observability/cost note.
- Status: closed
- Origin: initial

## New findings

None. No regression, security, or critical issue was introduced by the revision.

## Checks run

- `openspec validate harden-build-packaging --strict` → PASS ("Change 'harden-build-packaging' is valid", exit 0).
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → PASS (OpenSpec strict, spec-lint, verdict-lint; before this verdict).
- Reviewed artifacts at `2f57e0f0d346b120e1aabec13fbdaa81f986a9fd`; `git show HEAD:…/design.md` and `…/tasks.md` hashes equal the worktree files (`28ebef22…` and `89c1c5d1…`).
- Spec immutability: `git diff --stat 2a7f035..HEAD -- proposal.md specs/` is empty; the spec hash is `ac36671a8311d07946548b0c0873b4369871875c27c45e4f9328780357ba6748` at both SHAs.
- Coverage: 11 requirements, 38 scenarios, 24 checkbox tasks in 7 dependency-ordered groups; every requirement and scenario maps to a task or a Verification assertion.
- CI form: current `ci.yml#L48-L51` already uses `working-directory: backend` + `PYTHONPATH=.. poetry run python -m unittest discover -s tests -v`; `poetry -C backend` cwd change reproduced (Poetry 2.5.1).
- Rust command: `cargo build --manifest-path engine-rs/Cargo.toml --bin definitely-not-a-bin` reports "no bin target named … available bin targets: robotrader-node", confirming the workspace-root `--bin robotrader-node` form resolves.
- Helm v4.2.3 helper probe (temporary chart, described D8 logic): absent/empty → `5.0`; `7.5` → `7.5`; `-1` and `--set-string …=abc` → non-zero with the `fail` message, no `%!f(...)`; explicit `0` → `5.0` (noted as follow-up).
- Stale-lock block executed verbatim: expected non-zero with `cannot update the lock file … --locked`, post-check clean, manifest restored.
- `litellm`: current `pyproject.toml#L14` declares it; current lock has the package block at `#L1628` and the `strands-agents` extras label at `#L3176`; the plan's residual statement matches reality.
- `grep -rn '3\.16'` over the change directory → no match.
- Resolver/callers: `state_store.py#L734-L830`, `server.py#L99-L336`, `trading.py#L30-L63`, `orchestrator.py#L1020-L1052`; the endpoint/side-effect matrix matches the code paths.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "plan",
  "round": 2,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "2f57e0f0d346b120e1aabec13fbdaa81f986a9fd",
  "verdict": "APPROVE",
  "summary": "All ten R1 findings are closed at 2f57e0f; zero open blocker/major/minor/nit, the spec is unchanged, and no new finding qualifies. Non-blocking follow-up: D8/R4 say an explicit zero fails, but Sprig empty 0 renders 5.0; correct the wording in DEV without changing behaviour.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L38; design.md#L110,L208-L211; tasks.md#L260-L261",
      "evidence": "Task 5.1 restores working-directory: backend with PYTHONPATH=.. poetry run python -m unittest discover -s tests -v and states the root working directory for the --manifest-path build; the CI wiring block greps both accepted forms. Poetry 2.5.1 was re-verified to change cwd under -C.",
      "required_fix": "Use the existing working-directory form or state the corrected PYTHONPATH/-s values; state the build step's root working directory."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L102,L115-L120; tasks.md#L12-L13; backend/agents/trading.py#L30; backend/server.py#L324",
      "evidence": "D5 specifies MetaAllocatorAgent.apply_regime_preset(preset, commit: bool = True) in backend/agents/trading.py, keeps eager SET_REGIME/chat defaults, and makes /policy/regime commit after the backtest; the footprint note names trading.py and task 1.5 tests both behaviours. The current signature and callers were confirmed.",
      "required_fix": "Add trading.py to the footprint and task 1.4, preserve eager SET_REGIME/chat commits, and test both behaviours."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L105,L155-L160; tasks.md#L23,L131-L139",
      "evidence": "D8/R4 now define absent/empty -> 5.0, otherwise float64 + le 0 + fail, valid -> printf %.1f. On Helm v4.2.3 the described helper renders 5.0 for absent/empty, 7.5 for 7.5, and exits non-zero with the fail message for -1 and --set-string abc, with no %!f(...). Negative/non-numeric assertions are in tasks and Verification. Residual follow-up: Sprig empty 0 makes an explicit 0 render 5.0 rather than fail; safe and outside the spec scenario.",
      "required_fix": "Make D8 and R4 agree and validate or narrow the invalid-value claims; add negative/non-numeric render assertions."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L178-L199",
      "evidence": "The check now uses mktemp, an EXIT trap, a clean-tree precondition and post-check, and an inverted cargo --locked check, and justifies the local proxy. Executed at this SHA: the locked build failed with the lockfile error, the post-check reported a clean tree, and the manifest was restored.",
      "required_fix": "Use mktemp plus an EXIT trap, assert a clean tree, and justify the local proxy or run through Docker."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L171-L181; tasks.md#L45,L211-L215; specs/build-packaging/spec.md#L250-L254",
      "evidence": "R8 and task 6.1 state the residual explicitly: no litellm package block, but strands-agents extras metadata may name litellm; the gate is the package-block grep plus no litellm in pyproject plus a clean poetry check --lock. The current lock shows both the block and the extras label, matching the statement. Ruling: this satisfies the approved scenario under the dependency-declaration reading; requirement 11 makes literal string absence unsatisfiable, and no hidden spec narrowing occurs, so no spec-gap escalation is needed.",
      "required_fix": "Keep the package-block gate and state the residual explicitly; escalate only if the scenario is meant as literal string absence."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L101; tasks.md#L11",
      "evidence": "D4 now puts only the pure RustBinaryNotFoundError in backend/core/errors.py and lazy-imports JSONResponse inside the handler; task 1.3 states the lazy import and purpose, so state_store.py importing the exception does not pull FastAPI into the resolver path.",
      "required_fix": "Split the pure exception from the FastAPI handler or lazy-import the web dependency; otherwise correct the rationale."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "tasks.md#L58-L277",
      "evidence": "The Verification section now asserts the default env set and no Ingress, the .dockerignore lock removal and Dockerfile copy/locked/release lines, README/AGENTS build-step text, the no-compiler and both-methods assertions, CI job and path-filter presence, and the strands follow-up with a documented PR deferral rule.",
      "required_fix": "Add explicit commands/assertions or name the evidence source for each scenario."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L111; tasks.md#L13",
      "evidence": "D14 and task 1.5 specify child resets of kill_switch_active and policy before each case, /risk/kill last, tolerance of daemon workers, and the parent assertion that backend.server is not in sys.modules. Existing backend/tests references to backend.server are only the string assertions in test_health.py.",
      "required_fix": "Specify child state reset/order and the parent's sys.modules assertion."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L36-L38; tasks.md#L40,L258",
      "evidence": "The Context drops the untested Helm 3.16+ claim and explicitly says no Helm 3.x render is claimed; grep -rn '3\\.16' over the change directory returns no match, and the v4.2.3 pin remains in D13, task 5.3, and the CI wiring grep.",
      "required_fix": "Add a Helm 3.x render check or drop the claim; keep the v4.2.3 pin."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "design.md#L192-L201",
      "evidence": "The new Observability and cost subsection records the 503 access-log signal with no new metric/alert, /api/v1/health as the liveness signal, one extra Helm CI job plus a cached debug Rust build, and the litellm dependency-graph/image-install reduction with no runtime LLM-spend change.",
      "required_fix": "Add a short observability/cost note."
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
    "PLAN-R1-F10"
  ]
}
```
