# PLAN Review — Round 1

## Summary

CHANGES_REQUESTED at `b3718a8`: three majors, five minors, two nits, zero blockers. The resolver/503 design is sound and the approved spec is unchanged, but three plan defects block execution. Task 5.1's `poetry -C backend run ... -s backend/tests` runs with cwd=`backend` (Poetry changes directory), so the start directory and `PYTHONPATH=.` are wrong. Task 1.4 depends on `apply_regime_preset(preset, commit=False)`, which does not exist; it requires `backend/agents/trading.py`, missing from the Impact and footprint notes. D8/R4 claim `printf "%.1f"` rejects non-numeric values and falls back for non-positive ones; Helm v4.2.3 renders `%!f(...)` and exits 0. Risk rulings: the two extra files are justified and documented (footprint incomplete); the stale-lock check proves `--locked` but is not hermetic; the `litellm` package-block gate is robust; the subprocess 503 test is stable with child-state reset; Helm v4.2.3 is acceptable and Helm 3-only clusters are unaffected.

## Checklist walk (sdlc/checklists/plan.md)

| Section | Result | Evidence |
|---|---|---|
| 1. Traceability | PASS / UNCLEAR | D1–D16 map to the specs; all 11 requirements have tasks; the spec is byte-identical to the approved `2a7f035`. F02 exposes an undeclared production file; F05 narrows a spec scenario in design. |
| 2. Decisions | FAIL | D8's "non-numeric value fails the render loudly" is false (F03); all other alternatives/rejections are technical; the reversibility column separates D6/D11 one-way doors. |
| 3. Contracts and data | PASS / N/A | Success paths unchanged; the 503 error contract is defined once; `PolicyEnvelope`, IPC, DB, and cross-chain paths are untouched. |
| 4. Hot path and performance | PASS / N/A | No hot-path or `HardRiskGate` change; resolver is O(1); missing-binary failure is explicit. |
| 5. Safety and security | FAIL | Kill switch stays eager (D6) and the detail carries no secrets, but env-value validation is incomplete (F03). |
| 6. Test strategy | FAIL | Resolver/handler unit tests, subprocess integration, and negative checks are planned; several scenarios lack an explicit command/assertion (F07) and the child worker state is unspecified (F08). |
| 7. Rollout and rollback | PASS / FAIL | Deployment order and the digest-based rollback are concrete; observability and cost impact are absent (F10). |
| 8. Tasks | FAIL | 24 checkboxes in 7 dependency-ordered groups; task 1.4 is not executable as written (F02); verification is root-runnable except the internal CI command (F01). |

## Findings

### PLAN-R1-F01 — [major] CI discovery command is invalid under `poetry -C backend`
- Location: `openspec/changes/harden-build-packaging/tasks.md#L38`; `.github/workflows/ci.yml#L36-L51`
- Evidence: Task 5.1 prescribes `PYTHONPATH=. poetry -C backend run python -m unittest discover -s backend/tests -v` "from the repository root". Poetry 2.5.1 changes the process cwd to the `-C` target: `poetry -C backend run python -c "import os; print(os.getcwd())"` printed `.../.worktrees/9-harden-build-packaging/backend`. The start directory therefore resolves to `backend/backend/tests`, and `PYTHONPATH=.` points at `backend`, not the repo root, so `import backend.*` fails. The current job avoids this with `working-directory: backend` and `PYTHONPATH=..` (`ci.yml#L48-L51`).
- Required fix: Use the existing form (`working-directory: backend`, `PYTHONPATH=.. poetry run python -m unittest discover -s tests -v`), or keep `poetry -C backend` but set `PYTHONPATH=..` and `-s tests`. State the build step's working directory explicitly (repo root) so `--manifest-path engine-rs/Cargo.toml` resolves. Update task 5.1 and the CI evidence assertion accordingly.
- Status: open
- Origin: initial

### PLAN-R1-F02 — [major] Task 1.4 requires an undeclared `backend/agents/trading.py` change
- Location: `openspec/changes/harden-build-packaging/tasks.md#L12`; `design.md#L101,L114-L117`; `backend/agents/trading.py#L30-L63`; `backend/server.py#L324`
- Evidence: Task 1.4 calls `apply_regime_preset(preset, commit=False)`, but the method signature is `def apply_regime_preset(self, preset: str) -> PolicyEnvelope` and it calls `self.store.set_policy(env)` in all three branches (`trading.py#L39,L56,L62`). The design's footprint note says only two files are added beyond the proposal (`errors.py`, `test_missing_binary.py`), and the proposal Impact lists only `state_store.py` and `server.py` for production code. Implementing `commit=False` without changing `trading.py` would require the rejected revert-on-error alternative (D5), and leaving the default unchanged is required to keep `SET_REGIME`/`/chat` eager (`trading.py#L25`, `orchestrator.py#L1021,L1036`).
- Required fix: Add `backend/agents/trading.py` to the design footprint note and to task 1.4: introduce a `commit: bool = True` parameter (or an equivalent non-mutating builder) and keep `handle_message`/`SET_REGIME` committing eagerly. Add a test that `SET_REGIME` still persists the policy and that `/policy/regime` does not.
- Status: open
- Origin: initial

### PLAN-R1-F03 — [major] Budget helper claims are false for non-numeric and negative values
- Location: `design.md#L104` (D8), `design.md#L152-L155` (R4), `tasks.md#L23`
- Evidence: D8 says "a non-numeric value fails the render loudly" and R4 says the helper "falls back to `5.0` for empty, absent, or non-positive values". A faithful Helm v4.2.3 implementation of D8 (empty/zero fallback, otherwise `printf "%.1f"`) rendered `"%!f(int64=-1)"` for `--set env.maxDailyLlmBudgetUsd=-1`, `"%!f(string=a)"` for `--set-string env.maxDailyLlmBudgetUsd=abc`, and exited 0 in both cases. `printf "%.1f"` neither fails nor falls back for those inputs. The spec's required empty-string fallback does work (`""` → `"5.0"`), but the stated mitigation for invalid values does not.
- Required fix: Make D8 and R4 agree. Either add explicit numeric/positive validation in `robotrader.maxDailyLlmBudgetUsd` (e.g. `float64` plus `le 0`/`fail`, with a defined non-numeric policy) and add a negative/non-numeric render assertion, or narrow R4/D8 to the spec's empty-string case and document that other invalid values render an error marker. Do not claim a fallback that the helper does not implement.
- Status: open
- Origin: initial

### PLAN-R1-F04 — [minor] Stale-lock negative check is not hermetic and does not exercise the image build
- Location: `tasks.md#L137-L147`
- Evidence: The check backs up `engine-rs/crates/node/Cargo.toml` to the fixed path `/tmp/robotrader-node-Cargo.toml.bak`, appends a dependency, runs `cargo build --release --locked`, then restores with a plain `cp`. It has no `trap`, so an aborted or `set -e` run skips the restore; concurrent worktrees share `/tmp` and can clobber the backup; nothing asserts the worktree is clean afterwards. The `--locked` behavior itself is correct: in an isolated copy I reproduced `error: cannot update the lock file ... because --locked was passed to prevent this`. The check runs local `cargo build`, not the Docker builder stage, while the spec scenario is "the image is built".
- Required fix: Use `mktemp` for the backup, restore in an `EXIT` trap, and assert `git status --porcelain -- engine-rs/crates/node/Cargo.toml` is empty. Either run the negative check through `docker build -f Dockerfile.backend` or state why the local `--locked` run is an equivalent proxy for the builder stage.
- Status: open
- Origin: initial

### PLAN-R1-F05 — [minor] `litellm` residual in `strands-agents` extras vs the spec's literal "neither file declares"
- Location: `design.md#L166-L171` (R8); `tasks.md#L156-L159`; `specs/build-packaging/spec.md#L250-L254`
- Evidence: I simulated the lock regeneration in a copy (remove `litellm` from `pyproject.toml`, run `poetry lock`). The result has no `[[package]] name = "litellm"` block, but the `strands-agents` `[package.extras]` metadata still contains `litellm = [...]` and the `all` extra string. The plan's package-block + `poetry check --lock` gate is robust for the resolved dependency graph, but the spec scenario says "neither file declares `litellm`", which a raw reader can read as false.
- Required fix: Keep the package-block gate, and make the evidence explicit: `grep -n '^name = "litellm"$'` has no match while the `strands-agents` extras label remains as metadata. If the scenario is meant literally, escalate the wording as `spec-gap` (`declares` → `resolves/installs`) rather than silently narrowing it in design.
- Status: open
- Origin: initial

### PLAN-R1-F06 — [minor] `backend/core/errors.py` contradicts the "state store stays web-free" rationale
- Location: `design.md#L99-L100` (D3/D4); `tasks.md#L11`
- Evidence: D3 rejects raising `HTTPException` because it "imports FastAPI into the state store", and D4 rejects putting the error in `state_store.py` because it "gains a web dependency". Task 1.3 puts `RustBinaryNotFoundError` and the FastAPI handler in one `backend/core/errors.py`; the resolver in `state_store.py` must import the exception, so a module-level `JSONResponse`/FastAPI import in `errors.py` is transitive into the state store.
- Required fix: Split the pure exception from the FastAPI handler (handler in `server.py` or a separate HTTP module), or import `JSONResponse` lazily, so the stated boundary holds; otherwise correct the D3/D4 rationale.
- Status: open
- Origin: initial

### PLAN-R1-F07 — [minor] Several spec scenarios lack an explicit verification command or assertion
- Location: `tasks.md#L52-L203`
- Evidence: The `## Verification` section is root-runnable and covers most scenarios, but these have no named assertion: the default Deployment env set (`OPENROUTER_API_KEY`, `SOLANA_RPC_URL`, `REDIS_URL`, positive `MAX_DAILY_LLM_BUDGET_USD`); `.dockerignore` no longer excluding `engine-rs/Cargo.lock`; the build step present in `README.md`/`AGENTS.md`; "No compiler is invoked" (no mock asserting `subprocess.run` is not called); "Both methods use the selected binary"; "Existing CI jobs and triggers are retained" (only `sdlc-checks.yml` is diffed); and the `strands-agents` follow-up. Task-level `(covers:)` labels are not substitutes for the verification contract.
- Required fix: Add explicit commands/assertions for these scenarios (e.g. `grep -q 'cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node' README.md AGENTS.md`, `! grep -q 'engine-rs/Cargo.lock' .dockerignore`, a no-compiler mock assertion, a both-methods release-only test, and a CI-job presence check), or state the evidence source (docs diff, issue/PR body) where a command is not applicable.
- Status: open
- Origin: initial

### PLAN-R1-F08 — [minor] Subprocess 503 test starts live workers and shares mutable store state
- Location: `design.md#L110` (D14); `tasks.md#L13`
- Evidence: `backend/server.py#L34-L36` starts `state_store.start_live_worker` and `orchestrator.start_cognitive_scheduler` at import. In the child these are daemon threads, so they do not block process exit, but they call `run_rust_backtest`/live-tick/reflection paths and share the singleton store. The test exercises `/risk/kill` (a persistent mutation) before `/chat` and `/policy/regime`, so ordering or reset is required for the "regime remains applied" and "pre-request policy" assertions. The parent suite is genuinely isolated only if it never imports `backend.server`.
- Required fix: Specify in task 1.5 that the child resets `kill_switch_active`/policy between cases (or orders `/risk/kill` last), that the parent asserts `backend.server` is not in `sys.modules`, and that daemon workers are tolerated. This makes the stated "suite free of the live worker" precise.
- Status: open
- Origin: initial

### PLAN-R1-F09 — [nit] Helm 3.16+ compatibility is claimed but only Helm v4.2.3 is verified
- Location: `design.md#L36-L37`; `tasks.md#L40`
- Evidence: The design says Helm 4.2.3 was used locally and "renders under Helm 3.16+ as well"; the CI job is pinned to v4.2.3 only. The chart remains `apiVersion: v2` and uses standard helpers, so a Helm 3-only cluster is unaffected by the CI pin (rendering is client-side; clusters do not run Helm). The compatibility claim itself has no check.
- Required fix: Either add a Helm 3.x render check to the job (version matrix) or drop the untested "3.16+" claim; keep the v4.2.3 pin.
- Status: open
- Origin: initial

### PLAN-R1-F10 — [nit] No observability or cost-impact statement
- Location: `design.md#L137-L215`
- Evidence: The plan checklist asks for observability and cost impact. The design has Risks, Migration, and Rollback but no note that missing-binary 503s surface only in access logs (no new metric/alert) and no CI/Docker cost delta (one Helm job, one debug Rust build, dependency removal).
- Required fix: Add a short observability/cost note: 503 detail is in access logs; no new metric; CI gains a Helm job and a cached debug build; removing `litellm` reduces the dependency graph.
- Status: open
- Origin: initial

## Checks run

- `openspec validate harden-build-packaging --strict` → PASS ("Change 'harden-build-packaging' is valid", exit 0).
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → PASS (OpenSpec strict, spec-lint, verdict-lint; before this verdict).
- Spec immutability: `git show 2a7f035:openspec/changes/harden-build-packaging/specs/build-packaging/spec.md | shasum -a 256` equals the worktree hash (`ac36671a...`); `git diff --stat 2a7f035..HEAD -- proposal.md specs/` is empty.
- Reviewed artifacts read at `b3718a88ef491057d3068571b38c8d6fe6311a8c` (`design.md`, `tasks.md`).
- Task count: 24 checkboxes in 7 numbered groups; requirement/scenario map: 11 requirements, 38 scenarios (counted in `spec.md`).
- Resolver/call-site verification: `state_store.py#L734-L830`, `server.py#L99-L346`, `trading.py#L30-L63`, `orchestrator.py#L1021-L1051`.
- Poetry cwd: `poetry -C backend run python -c "import os; print(os.getcwd())"` → `.../backend`; `PYTHONPATH=. poetry -C backend run python -c ...` → cwd `backend`.
- Helm: `helm version` → v4.2.3; `helm template charts/robotrader` currently fails on missing `robotrader.fullname`; helper probes confirmed `""` → `"5.0"`, `-1` → `"%!f(int64=-1)"`, `abc` → `"%!f(string=a)"`, exit 0.
- Stale lock: isolated copy with `thiserror.workspace = true` appended → `cargo build --release --locked` fails with "cannot update the lock file ... because --locked was passed".
- `litellm`: isolated `poetry lock` without the dependency → no `[[package]] name = "litellm"`, but `strands-agents` extras still contain the string.
- `poetry -C backend check --lock` → "All set!" (exit 0). `httpx 0.28.1` is present in the lock via `solana`/`mcp`.
- Markers: `backend/__init__.py` and `backend/tests/__init__.py` are absent now (consistent with task 2.1). `test_health.py` deliberately avoids `backend.server`; `test_architecture.py`, `test_hierarchy_v3.py`, and `test_metrics_populations.py` invoke the Rust resolver.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "b3718a88ef491057d3068571b38c8d6fe6311a8c",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Three majors and five minors remain: the CI discovery command is invalid under poetry -C, task 1.4 requires an undeclared trading.py change, and the budget helper's invalid-value claims are false. No blockers; the resolver/503 design and spec are otherwise sound.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/tasks.md#L38; .github/workflows/ci.yml#L36-L51",
      "evidence": "Task 5.1 prescribes `PYTHONPATH=. poetry -C backend run python -m unittest discover -s backend/tests -v`; Poetry 2.5.1 changes cwd to the -C target (verified: cwd printed .../backend), so the start dir resolves to backend/backend/tests and PYTHONPATH=. points at backend. The current job uses working-directory: backend and PYTHONPATH=.. .",
      "required_fix": "Use the existing working-directory/PYTHONPATH=.. form, or keep poetry -C backend with PYTHONPATH=.. and -s tests; state the build step's repo-root working directory."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/tasks.md#L12; design.md#L101,L114-L117; backend/agents/trading.py#L30-L63; backend/server.py#L324",
      "evidence": "Task 1.4 calls apply_regime_preset(preset, commit=False), but the method takes only preset and commits via self.store.set_policy in all three branches. Implementing commit=False requires backend/agents/trading.py, which is absent from the proposal Impact and from the design's two-extra-file footprint note; the default must stay committing for SET_REGIME/chat.",
      "required_fix": "Add backend/agents/trading.py to the footprint and task 1.4 (commit: bool = True or a non-mutating builder), preserve eager SET_REGIME/chat commits, and add tests for both behaviours."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L104,L152-L155; tasks.md#L23",
      "evidence": "D8 claims a non-numeric value fails the render loudly and R4 claims a fallback for non-positive values. A faithful Helm v4.2.3 helper (empty/zero fallback + printf \"%.1f\") rendered %!f(int64=-1) for -1 and %!f(string=a) for abc, exiting 0; only the empty-string case returns 5.0.",
      "required_fix": "Add explicit numeric/positive validation (float64 plus le/fail, with a defined non-numeric policy) and a negative/non-numeric render assertion, or narrow D8/R4 to the spec's empty-string case."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L137-L147",
      "evidence": "The stale-lock check uses the fixed /tmp/robotrader-node-Cargo.toml.bak, a plain cp restore with no trap, and no dirty-tree assertion; concurrent worktrees can collide. The --locked failure was reproduced in an isolated copy, but the check runs local cargo, not the Docker builder stage the spec scenario names.",
      "required_fix": "Use mktemp plus an EXIT trap, assert git status --porcelain is clean, and either run the check through docker build or justify the local --locked proxy."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L166-L171; tasks.md#L156-L159; specs/build-packaging/spec.md#L250-L254",
      "evidence": "A simulated poetry lock without litellm has no [[package]] name = \"litellm\" block but the strands-agents [package.extras] metadata still contains the litellm string. The package-block gate is robust, but the spec scenario says neither file declares litellm.",
      "required_fix": "Keep the package-block + poetry check --lock gate and state the residual extras metadata explicitly in evidence; if the scenario is literal, escalate the wording as spec-gap."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L99-L100; tasks.md#L11",
      "evidence": "D3 rejects HTTPException because it imports FastAPI into the state store and D4 rejects state_store.py for gaining a web dependency, but task 1.3 places the exception and the FastAPI handler in one errors.py that state_store.py must import, making a module-level FastAPI import transitive.",
      "required_fix": "Split the pure exception from the FastAPI handler or import JSONResponse lazily; otherwise correct the D3/D4 rationale."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "tasks.md#L52-L203",
      "evidence": "The Verification section has no explicit assertion for the default Deployment env set, the .dockerignore lockfile removal, the docs build step, the no-compiler invariant, both methods selecting the binary, existing CI-job retention, or the strands follow-up; task (covers:) labels do not substitute for the verification contract.",
      "required_fix": "Add explicit commands/assertions (or state the docs-diff/issue-body evidence source) for each of these scenarios."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L110; tasks.md#L13",
      "evidence": "backend/server.py#L34-L36 starts the live worker and cognitive scheduler at import; the child runs them as daemon threads and shares the singleton store, while the test exercises the persistent /risk/kill mutation alongside /chat and /policy/regime. Ordering or reset is needed; only the parent is genuinely worker-free.",
      "required_fix": "Specify child state reset/order in task 1.5 and assert the parent never imports backend.server."
    },
    {
      "id": "PLAN-R1-F09",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L36-L37; tasks.md#L40",
      "evidence": "The design claims the chart renders under Helm 3.16+ but only Helm v4.2.3 is verified or pinned. The chart is apiVersion v2 and rendering is client-side, so a Helm 3-only cluster is unaffected, but the compatibility claim is untested.",
      "required_fix": "Add a Helm 3.x render check or drop the 3.16+ claim; keep the v4.2.3 pin."
    },
    {
      "id": "PLAN-R1-F10",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "design.md#L137-L215",
      "evidence": "The design has no observability or cost-impact statement: missing-binary 503s surface only in access logs, no new metric/alert is planned, and the CI/Docker cost delta is unstated.",
      "required_fix": "Add a short observability/cost note (503 access-log signal, no new metric, one Helm job plus a cached debug build, dependency removal)."
    }
  ],
  "closed": []
}
```
