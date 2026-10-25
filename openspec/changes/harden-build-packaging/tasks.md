# Tasks — harden-build-packaging

Dependency order: the resolver and its error contract come first because the
Python suite and the container both depend on it; markers and docs follow; then
Helm, Docker, CI, and dependency cleanup. Every task stays inside one session.

## 1. Shared backtest resolver and 503 contract

- [x] 1.1 Add `resolve_robotrader_binary(engine_dir)` to `backend/core/state_store.py`: return `engine-rs/target/debug/robotrader-node` when present, otherwise `engine-rs/target/release/robotrader-node`, otherwise raise the typed error; never spawn a compiler. Refactor `run_rust_backtest` onto it. (covers: Debug build is used when present; Fresh debug build wins over release; Release is used as the fallback; No compiler is invoked)
- [x] 1.2 Route `run_rust_backtest_for_leaf` through the same resolver, keeping the existing `leaf-solana` delegation to `run_rust_backtest`. (covers: Both methods use the selected binary)
- [x] 1.3 Add `backend/core/errors.py` with the pure `RustBinaryNotFoundError` and a global handler that lazy-imports `JSONResponse` inside the function and returns HTTP 503 with `application/json` and a `detail` containing both candidate paths and `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node`; register the handler on the FastAPI app in `backend/server.py` and leave `/ws/chat` untouched. The lazy import keeps `state_store.py` free of a module-level web dependency. (covers: Actionable missing-binary error; Read endpoints return the uniform 503; Leaf backtest returns the uniform 503; Backtest mutation endpoint returns the uniform 503)
- [x] 1.4 Add `commit: bool = True` to `MetaAllocatorAgent.apply_regime_preset` in `backend/agents/trading.py`, committing with `set_policy` only when true so `handle_message`/`SET_REGIME` stays eager; make `/api/v1/policy/regime` pass `commit=False` and call `set_policy` only after the backtest succeeds; keep `/api/v1/risk/kill` and `/chat` regime changes eager. (covers: Policy regime does not apply on a missing binary; Kill switch applies despite the missing binary; Chat commands return the uniform 503)
- [x] 1.5 Add `backend/tests/test_missing_binary.py`: in-process resolver precedence over temporary engine directories (asserting no `subprocess.run`/`Popen` call when missing and the same binary for both methods), handler response shape, and a subprocess integration test (the `test_health.py` isolation pattern) that patches the resolver and exercises `/status`, `/hierarchy`, `/backtest/run`, the leaf backtest, `/policy/regime`, `/risk/kill`, `/chat`, and `/api/v1/health`. The child resets `kill_switch_active` and the policy before each case and runs `/risk/kill` last; the parent asserts `backend.server` is not in `sys.modules`; daemon workers in the child are tolerated because the child exits after its assertions. Add a case proving `SET_REGIME` still commits while `/policy/regime` does not. (covers: Read endpoints; Leaf backtest; Backtest mutation; Policy regime; Kill switch; Chat commands; Health and process survive a missing binary)

## 2. Python package markers and documented test procedure

- [x] 2.1 Add empty `backend/__init__.py` and `backend/tests/__init__.py`. (covers: Markers exist)
- [x] 2.2 Update `README.md` and `AGENTS.md` so the documented procedure runs `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` from the repository root before `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v`. (covers: Documented local procedure includes the build step)
- [x] 2.3 From a clean `engine-rs/target/` state, follow the documented build-then-test procedure and confirm discovery loads every `test_*.py` module with no `Start directory is not importable` error. (covers: Discovery loads every test module; Discovery is stable across supported Python versions)

## 3. Helm chart

- [x] 3.1 Add `charts/robotrader/templates/_helpers.tpl` defining `robotrader.fullname`, `robotrader.labels`, `robotrader.selectorLabels`, and `robotrader.maxDailyLlmBudgetUsd` with the empty/absent `5.0` fallback, the `float64` + `le 0` `fail` guard for non-numeric/zero/negative values, and `printf "%.1f"` formatting for valid values. (covers: Default render succeeds; Lint succeeds)
- [x] 3.2 Add `charts/robotrader/templates/service.yaml` using `.Values.service.type`, `.Values.service.port`, numeric `targetPort: 8000`, and the same selector labels as the pod template. (covers: Service matches the deployment pods)
- [x] 3.3 Add `charts/robotrader/templates/ingress.yaml`, rendered only when `.Values.ingress.enabled` is true, using `networking.k8s.io/v1` and the configured host and path. (covers: Ingress renders when enabled; No Ingress when disabled)
- [x] 3.4 Extend `charts/robotrader/templates/deployment.yaml` with `REDIS_URL` and `MAX_DAILY_LLM_BUDGET_USD`, preserving `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`. (covers: Default environment values are valid; Explicit environment overrides are rendered; Empty budget override falls back to a valid number)
- [x] 3.5 Add documented `env.redisUrl: ""` and `env.maxDailyLlmBudgetUsd: 5.0` defaults plus `ingress.host` and `ingress.path` to `charts/robotrader/values.yaml`, with a comment line naming each env key. (covers: Default environment values are valid; Ingress renders when enabled)

## 4. Docker image

- [x] 4.1 Remove the `engine-rs/Cargo.lock` exclusion from `.dockerignore`. (covers: Lockfile is in the build context)
- [x] 4.2 In `Dockerfile.backend`, copy `engine-rs/Cargo.toml` and `engine-rs/Cargo.lock` before `engine-rs/crates`, and build with `cargo build --release --locked --bin robotrader-node`. (covers: Lockfile is in the build context; Inconsistent lockfile fails the build)
- [x] 4.3 Copy the release binary to `/app/engine-rs/target/release/robotrader-node` and remove the `target/debug` copy. (covers: Release binary is installed)
- [x] 4.4 Build the image and assert the release path exists and is executable while the debug path is absent. (covers: Release binary is installed)

## 5. CI

- [x] 5.1 Add the Rust toolchain and a repository-root `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` step to the Python job before dependency installation. Keep the discovery step in its existing `working-directory: backend` form with `PYTHONPATH=.. poetry run python -m unittest discover -s tests -v`; do not use `poetry -C backend` with `-s backend/tests`, because Poetry changes cwd. The root-level `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` command remains the documented local procedure. (covers: Python CI job builds the binary before the suite)
- [x] 5.2 Add `charts/**` to `pull_request.paths` and `push.paths` in `.github/workflows/ci.yml`. (covers: Chart-only change triggers the Helm job; Existing CI jobs and triggers are retained)
- [x] 5.3 Add the `helm` job with pinned Helm `v4.2.3`, `helm lint charts/robotrader`, `helm template charts/robotrader`, `helm show values` key/comment assertions, and render assertions for the empty override (`5.0`) plus the non-numeric and negative `fail` cases. (covers: Chart-only change triggers the Helm job; Helm regression fails CI; Existing CI jobs and triggers are retained; Helm version is pinned; Default environment values are valid)
- [x] 5.4 Confirm `.github/workflows/sdlc-checks.yml` is unchanged by the branch. (covers: Existing CI jobs and triggers are retained)

## 6. Dependency cleanup and follow-up

- [x] 6.1 Remove `litellm` from `backend/pyproject.toml`, delete `backend/config.py`, regenerate `backend/poetry.lock` with `poetry -C backend lock`, and confirm the lock has no `litellm` package block and no module imports `litellm` or `backend.config`. Record in the evidence that `strands-agents`'s extra metadata still names `litellm`; that label is package metadata, not a resolved dependency, and satisfying a literal string-absence reading would require removing `strands-agents`, which requirement 11 forbids. (covers: litellm is absent; backend config module is removed; Lockfile is consistent; No module imports the removed dependency or config)
- [ ] 6.2 Keep `strands-agents` declared and record the wire-or-remove follow-up in the issue logbook and the PR body, citing `docs/agents.md` and ADR-0001 that still claim it. Evidence source: the issue comment and PR body, checked with `gh issue view 9` and `gh pr view`. (covers: strands-agents remains declared; Follow-up is recorded)

## 7. End-to-end verification

- [ ] 7.1 Run every command in `## Verification` from the repository root and attach the output to the issue and the PR as evidence. (covers: all eleven requirements)

## Verification

Run from the repository root. Attach the commands and their output as evidence.

### Build and test

```bash
cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node
```
Expected: exit 0 and `engine-rs/target/debug/robotrader-node` exists.

```bash
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v
```
Expected: exit 0; every `test_*.py` module under `backend/tests` is listed; no
`Start directory is not importable` error.

```bash
PYTHONPATH=. python3 -m unittest backend.tests.test_missing_binary -v
```
Expected: exit 0; resolver precedence cases pass; the missing-binary case asserts
no `subprocess.run` or `Popen` call; both `run_rust_backtest` and
`run_rust_backtest_for_leaf` select the same binary; the 503 `detail` contains
both candidate paths and the `--manifest-path` build command; `/api/v1/health`
stays 200 while the other endpoints return 503; `/policy/regime` leaves the
effective policy unchanged; `/risk/kill` leaves the kill switch active; `/chat`
keeps the applied regime; `SET_REGIME` still commits; the parent test asserts
`backend.server` is not in `sys.modules`.

The discovery command is run under the CI Python 3.11 and the local `python3`
version; both must exit 0 and report no `Start directory is not importable`
error (evidence: the CI log and the local run).

### Helm

```bash
helm lint charts/robotrader
```
Expected: exit 0 with no `[ERROR]` line.

```bash
helm template charts/robotrader
```
Expected: exit 0; exactly one `kind: Deployment` and one `kind: Service`; no
`kind: Ingress`.

```bash
rendered="$(helm template charts/robotrader)"
grep -q 'name: OPENROUTER_API_KEY' <<<"$rendered"
grep -q 'name: SOLANA_RPC_URL' <<<"$rendered"
grep -q 'name: REDIS_URL' <<<"$rendered"
grep -q 'name: MAX_DAILY_LLM_BUDGET_USD' <<<"$rendered"
budget="$(awk '/name: MAX_DAILY_LLM_BUDGET_USD/{getline; gsub(/[" ]/, "", $2); print $2}' <<<"$rendered")"
python3 -c 'import sys; sys.exit(0 if float(sys.argv[1]) > 0 else 1)' "$budget"
test "$(grep -c 'kind: Ingress' <<<"$rendered" || true)" -eq 0
```
Expected: every command exits 0; the default render keeps the OpenRouter and
Solana environment, provides `REDIS_URL` and a positive numeric
`MAX_DAILY_LLM_BUDGET_USD`, and renders no Ingress.

```bash
helm template charts/robotrader --set ingress.enabled=true \
  --set ingress.host=robotrader.example.test --set ingress.path=/
```
Expected: one `kind: Ingress` with host `robotrader.example.test`, path `/`, and
a backend pointing at the chart's Service.

```bash
helm template charts/robotrader --set env.redisUrl=redis://cache:6379/0 \
  --set env.maxDailyLlmBudgetUsd=7.5
```
Expected: `REDIS_URL` value `redis://cache:6379/0`; `MAX_DAILY_LLM_BUDGET_USD`
value `7.5`.

```bash
helm template charts/robotrader --set env.maxDailyLlmBudgetUsd=""
```
Expected: `MAX_DAILY_LLM_BUDGET_USD` value `"5.0"`.

Negative validation cases (each must exit non-zero with the `fail` message, not
render `%!f(...)`):

```bash
helm template charts/robotrader --set env.maxDailyLlmBudgetUsd=-1
helm template charts/robotrader --set-string env.maxDailyLlmBudgetUsd=abc
```
Expected: both exit non-zero; the message names `env.maxDailyLlmBudgetUsd` and
requires a positive number.

```bash
helm show values charts/robotrader
```
Expected: contains `redisUrl: ""`, `maxDailyLlmBudgetUsd: 5.0`, and a comment
line naming each key.

```bash
helm template charts/robotrader --show-only templates/service.yaml
helm template charts/robotrader --show-only templates/deployment.yaml
```
Expected: the Service `spec.selector` equals the Deployment
`spec.template.metadata.labels` (`app.kubernetes.io/name` and
`app.kubernetes.io/instance`); the Service targets port 8000.

### Docker

```bash
docker build -f Dockerfile.backend -t robotrader:verify .
```
Expected: exit 0.

```bash
! grep -qx 'engine-rs/Cargo.lock' .dockerignore
grep -q 'engine-rs/Cargo.toml' Dockerfile.backend
grep -q 'engine-rs/Cargo.lock' Dockerfile.backend
grep -q -- '--locked' Dockerfile.backend
grep -q -- '--release' Dockerfile.backend
```
Expected: all exit 0; the lock is in the build context, the builder copies it
before the crates, and the build is locked and release.

```bash
docker run --rm --entrypoint sh robotrader:verify -c \
  'test -x /app/engine-rs/target/release/robotrader-node && test ! -e /app/engine-rs/target/debug/robotrader-node'
```
Expected: exit 0.

Controlled negative check for the stale-lock failure. It is hermetic (`mktemp`,
`EXIT` trap, clean-tree precondition and post-check). The local `--locked` run is
a faithful proxy for the Docker builder: the builder's only relevant step is the
same `cargo build --release --locked` on the same manifest and lockfile, with the
base image and `COPY` adding no resolution behaviour.

```bash
manifest=engine-rs/crates/node/Cargo.toml
backup="$(mktemp)"
trap 'cp "$backup" "$manifest"; rm -f "$backup"' EXIT
cp "$manifest" "$backup"
test -z "$(git status --porcelain -- "$manifest")"
printf '\nthiserror.workspace = true\n' >> "$manifest"
if cargo build --release --locked --manifest-path engine-rs/Cargo.toml --bin robotrader-node; then
  echo 'expected the locked build to fail' >&2
  exit 1
fi
cp "$backup" "$manifest"
test -z "$(git status --porcelain -- "$manifest")"
```
Expected: the locked build exits non-zero with a lockfile-update error; the tree
is clean before and after; the trap restores the manifest on any exit.

### Dependencies

```bash
grep -n 'litellm' backend/pyproject.toml
```
Expected: no match.

```bash
grep -n '^name = "litellm"$' backend/poetry.lock
```
Expected: no match. Note the evidence explicitly: `strands-agents`'s
`[package.extras]` metadata may still contain the string `litellm`; that label
is copied package metadata, not a resolved dependency. A literal string-absence
reading would require removing `strands-agents`, which requirement 11 forbids;
the gate is the absence of a `litellm` package block plus a clean lock.

```bash
test ! -e backend/config.py
```
Expected: exit 0.

```bash
grep -RIn --include='*.py' -e 'import litellm' -e 'backend\.config' backend
```
Expected: no match.

```bash
poetry -C backend check --lock
poetry -C backend install --no-root
```
Expected: both exit 0.

```bash
grep -q 'strands-agents' backend/pyproject.toml
grep -q '^name = "strands-agents"$' backend/poetry.lock
gh issue view 9 --json comments --jq '.comments[].body' | grep -q 'strands-agents'
gh pr view --json body --jq '.body' | grep -q 'strands-agents'
```
Expected: all exit 0. The last two assert the recorded follow-up in the issue
logbook and the PR body; if the PR does not exist yet, record the evidence in
the issue logbook and state why the PR check is deferred to DEV.

### Documentation

```bash
grep -q 'cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node' README.md
grep -q 'cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node' AGENTS.md
grep -q 'PYTHONPATH=. python3 -m unittest discover -s backend/tests -v' README.md
grep -q 'PYTHONPATH=. python3 -m unittest discover -s backend/tests -v' AGENTS.md
```
Expected: all four exit 0; both documents put the build step before the discovery
command.

### CI wiring

```bash
test "$(grep -c 'charts/\*\*' .github/workflows/ci.yml)" -ge 2
grep -q 'version: v4.2.3' .github/workflows/ci.yml
grep -q 'cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node' .github/workflows/ci.yml
grep -q 'working-directory: backend' .github/workflows/ci.yml
grep -q 'PYTHONPATH=.. poetry run python -m unittest discover -s tests -v' .github/workflows/ci.yml
grep -q '^  rust:' .github/workflows/ci.yml
grep -q '^  python:' .github/workflows/ci.yml
grep -q '^  frontend:' .github/workflows/ci.yml
grep -q '"engine-rs/\*\*"' .github/workflows/ci.yml
grep -q '"backend/\*\*"' .github/workflows/ci.yml
grep -q '"frontend/\*\*"' .github/workflows/ci.yml
```
Expected: all exit 0. `charts/**` appears in both the pull-request and push
filters (count at least 2); the Rust build is root-runnable; the Python
discovery keeps its `backend` working directory and `PYTHONPATH=..` form; the
existing Rust, Python, and frontend jobs and their path filters remain.

```bash
git diff --quiet master...HEAD -- .github/workflows/sdlc-checks.yml
```
Expected: exit 0.

### SDLC gates

```bash
openspec validate harden-build-packaging --strict
scripts/sdlc/sdlc.sh check harden-build-packaging
```
Expected: both exit 0.
