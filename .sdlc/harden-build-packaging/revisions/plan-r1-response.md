stage: plan
round: 1
head_sha: b3718a88ef491057d3068571b38c8d6fe6311a8c
responses:
  - id: PLAN-R1-F01
    action: fixed
    evidence: >-
      tasks.md task 5.1 now keeps the Python CI job in its existing
      `working-directory: backend` form with `PYTHONPATH=.. poetry run python -m
      unittest discover -s tests -v`, and states that the Rust build step runs
      from the repository root with `--manifest-path engine-rs/Cargo.toml`.
      design.md D13 records the same form and the rejection of `poetry -C
      backend`; the Migration Plan distinguishes the CI form from the
      root-runnable local procedure. The Verification "CI wiring" block asserts
      `working-directory: backend`, `PYTHONPATH=..`, and the `-s tests` form, so
      the invalid command cannot regress.
  - id: PLAN-R1-F02
    action: fixed
    evidence: >-
      design.md D5 now specifies `MetaAllocatorAgent.apply_regime_preset(preset,
      commit: bool = True)` in `backend/agents/trading.py`, with the default
      preserving the eager `SET_REGIME`/chat commit and `/api/v1/policy/regime`
      passing `commit=False` then calling `set_policy` after the backtest. The
      footprint note names `backend/agents/trading.py` as a production file
      beyond the proposal's list. tasks.md task 1.4 is executable and task 1.5
      requires tests proving `SET_REGIME` still commits while `/policy/regime`
      does not.
  - id: PLAN-R1-F03
    action: fixed
    evidence: >-
      design.md D8 and R4 now define the helper precisely: absent/empty renders
      `5.0`; otherwise `float64` plus a `le 0` guard calls `fail` (Sprig coerces
      a non-numeric string to 0, so this also catches `abc`); valid values render
      through `printf "%.1f"`. The false "non-numeric fails the render loudly"
      and "non-positive falls back" claims are removed. tasks.md tasks 3.1 and
      5.3 and the Verification section add the `--set env.maxDailyLlmBudgetUsd=-1`
      and `--set-string env.maxDailyLlmBudgetUsd=abc` cases, each expected to
      exit non-zero with the helper's `fail` message rather than `%!f(...)`.
  - id: PLAN-R1-F04
    action: fixed
    evidence: >-
      The stale-lock check in tasks.md `## Verification` now uses `backup="$(mktemp)"`
      with an `EXIT` trap that restores the manifest and removes the backup, a
      clean-tree precondition and post-check via `git status --porcelain --
      engine-rs/crates/node/Cargo.toml`, and an inverted `if cargo build
      --release --locked ...` so a silent success fails the check. The block
      states why the local `--locked` run is an equivalent proxy for the Docker
      builder: the builder's only relevant step is the same command on the same
      manifest and lockfile; the image build itself is verified separately by
      `docker build` and the release-path `docker run` assertion.
  - id: PLAN-R1-F05
    action: fixed
    evidence: >-
      design.md R8 and tasks.md task 6.1 now state the residual explicitly: the
      regenerated lock has no `[[package]] name = "litellm"` block, but the
      `strands-agents` `[package.extras]` metadata may still contain the string
      `litellm`; that is copied package metadata, not a resolved dependency. The
      gate remains `grep -n '^name = "litellm"$'` with no match, no `litellm` in
      pyproject, and a clean `poetry -C backend check --lock`. No spec-gap is
      escalated because a literal string-absence reading is unsatisfiable while
      requirement 11 retains `strands-agents`; the evidence records this rather
      than narrowing the scenario silently.
  - id: PLAN-R1-F06
    action: fixed
    evidence: >-
      design.md D4 now specifies that `backend/core/errors.py` holds the pure
      `RustBinaryNotFoundError` and lazy-imports `JSONResponse` inside the
      handler, so `state_store.py` importing the exception does not pull FastAPI
      into the resolver path. The D3/D4 rationale is aligned; tasks.md task 1.3
      states the lazy import explicitly.
  - id: PLAN-R1-F07
    action: fixed
    evidence: >-
      tasks.md `## Verification` now has explicit assertions for every gap named
      in the finding: a default-render block asserting `OPENROUTER_API_KEY`,
      `SOLANA_RPC_URL`, `REDIS_URL`, and a positive numeric
      `MAX_DAILY_LLM_BUDGET_USD`; `! grep -qx 'engine-rs/Cargo.lock' .dockerignore`
      plus Dockerfile copy/locked/release greps; README/AGENTS build-step greps
      in a new "Documentation" block; the no-compiler and both-methods assertions
      in the expected output of `test_missing_binary`; CI job and path-filter
      presence greps; and `gh issue view 9` / `gh pr view` follow-up greps with a
      documented deferral rule when the PR does not yet exist.
  - id: PLAN-R1-F08
    action: fixed
    evidence: >-
      design.md D14 and tasks.md task 1.5 now specify that the child resets
      `kill_switch_active` and the policy before each case, runs `/risk/kill`
      last, and tolerates the daemon live-worker/scheduler because the child
      exits after its assertions. The parent test asserts `backend.server` is not
      in `sys.modules`, so the suite remains genuinely worker-free.
  - id: PLAN-R1-F09
    action: fixed
    evidence: >-
      design.md Context drops the untested "renders under Helm 3.16+" claim and
      states only that Helm v4.2.3 is the pinned verification tool, the chart
      remains `apiVersion: v2`, and a Helm 3-only cluster is unaffected because
      rendering is client-side. The v4.2.3 pin is retained in D13 and the CI
      verification.
  - id: PLAN-R1-F10
    action: fixed
    evidence: >-
      design.md adds an "Observability and cost" subsection under Risks /
      Trade-offs: missing-binary 503s surface in the access log with the
      actionable detail, no new metric or alert is added, `/api/v1/health`
      remains the liveness signal, CI gains one Helm job plus a cached debug Rust
      build, and removing `litellm` shrinks the dependency graph and image
      install step with no runtime LLM-spend change.
