# Tasks — harden-build-packaging

Dependency order: the resolver and its error contract come first because the
Python suite and the container both depend on it; markers and docs follow; then
Helm, Docker, CI, and dependency cleanup. Every task stays inside one session.

## 1. Shared backtest resolver and 503 contract

- [ ] 1.1 Add `resolve_robotrader_binary(engine_dir)` to `backend/core/state_store.py`: return `engine-rs/target/debug/robotrader-node` when present, otherwise `engine-rs/target/release/robotrader-node`, otherwise raise the typed error; never spawn a compiler. Refactor `run_rust_backtest` onto it. (covers: Debug build is used when present; Fresh debug build wins over release; Release is used as the fallback; No compiler is invoked)
- [ ] 1.2 Route `run_rust_backtest_for_leaf` through the same resolver, keeping the existing `leaf-solana` delegation to `run_rust_backtest`. (covers: Both methods use the selected binary)
- [ ] 1.3 Add `backend/core/errors.py` with `RustBinaryNotFoundError` and the global handler returning HTTP 503 with `application/json` and a `detail` containing both candidate paths and `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node`; register it on the FastAPI app in `backend/server.py` and leave `/ws/chat` untouched. (covers: Actionable missing-binary error; Read endpoints return the uniform 503; Leaf backtest returns the uniform 503; Backtest mutation endpoint returns the uniform 503)
- [ ] 1.4 Make `/api/v1/policy/regime` build the preset with `apply_regime_preset(preset, commit=False)` and call `set_policy` only after the backtest succeeds; keep `/api/v1/risk/kill` and `/chat` regime changes eager. (covers: Policy regime does not apply on a missing binary; Kill switch applies despite the missing binary; Chat commands return the uniform 503)
- [ ] 1.5 Add `backend/tests/test_missing_binary.py`: in-process resolver precedence over temporary engine directories, handler response shape, and a subprocess integration test (the `test_health.py` isolation pattern) that patches the resolver and exercises `/status`, `/hierarchy`, `/backtest/run`, the leaf backtest, `/policy/regime`, `/risk/kill`, `/chat`, and `/api/v1/health`. (covers: Read endpoints; Leaf backtest; Backtest mutation; Policy regime; Kill switch; Chat commands; Health and process survive a missing binary)

## 2. Python package markers and documented test procedure

- [ ] 2.1 Add empty `backend/__init__.py` and `backend/tests/__init__.py`. (covers: Markers exist)
- [ ] 2.2 Update `README.md` and `AGENTS.md` so the documented procedure runs `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` from the repository root before `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v`. (covers: Documented local procedure includes the build step)
- [ ] 2.3 From a clean `engine-rs/target/` state, follow the documented build-then-test procedure and confirm discovery loads every `test_*.py` module with no `Start directory is not importable` error. (covers: Discovery loads every test module; Discovery is stable across supported Python versions)

## 3. Helm chart

- [ ] 3.1 Add `charts/robotrader/templates/_helpers.tpl` defining `robotrader.fullname`, `robotrader.labels`, `robotrader.selectorLabels`, and `robotrader.maxDailyLlmBudgetUsd` with the `5.0` fallback and `printf "%.1f"` formatting. (covers: Default render succeeds; Lint succeeds)
- [ ] 3.2 Add `charts/robotrader/templates/service.yaml` using `.Values.service.type`, `.Values.service.port`, numeric `targetPort: 8000`, and the same selector labels as the pod template. (covers: Service matches the deployment pods)
- [ ] 3.3 Add `charts/robotrader/templates/ingress.yaml`, rendered only when `.Values.ingress.enabled` is true, using `networking.k8s.io/v1` and the configured host and path. (covers: Ingress renders when enabled; No Ingress when disabled)
- [ ] 3.4 Extend `charts/robotrader/templates/deployment.yaml` with `REDIS_URL` and `MAX_DAILY_LLM_BUDGET_USD`, preserving `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`. (covers: Default environment values are valid; Explicit environment overrides are rendered; Empty budget override falls back to a valid number)
- [ ] 3.5 Add documented `env.redisUrl: ""` and `env.maxDailyLlmBudgetUsd: 5.0` defaults plus `ingress.host` and `ingress.path` to `charts/robotrader/values.yaml`, with a comment line naming each env key. (covers: Default environment values are valid; Ingress renders when enabled)

## 4. Docker image

- [ ] 4.1 Remove the `engine-rs/Cargo.lock` exclusion from `.dockerignore`. (covers: Lockfile is in the build context)
- [ ] 4.2 In `Dockerfile.backend`, copy `engine-rs/Cargo.toml` and `engine-rs/Cargo.lock` before `engine-rs/crates`, and build with `cargo build --release --locked --bin robotrader-node`. (covers: Lockfile is in the build context; Inconsistent lockfile fails the build)
- [ ] 4.3 Copy the release binary to `/app/engine-rs/target/release/robotrader-node` and remove the `target/debug` copy. (covers: Release binary is installed)
- [ ] 4.4 Build the image and assert the release path exists and is executable while the debug path is absent. (covers: Release binary is installed)

## 5. CI

- [ ] 5.1 Add the Rust toolchain and `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` to the Python job before dependency installation, and run discovery from the repository root with `PYTHONPATH=. poetry -C backend run python -m unittest discover -s backend/tests -v`. (covers: Python CI job builds the binary before the suite)
- [ ] 5.2 Add `charts/**` to `pull_request.paths` and `push.paths` in `.github/workflows/ci.yml`. (covers: Chart-only change triggers the Helm job; Existing CI jobs and triggers are retained)
- [ ] 5.3 Add the `helm` job with pinned Helm `v4.2.3`, `helm lint charts/robotrader`, `helm template charts/robotrader`, `helm show values` key/comment assertions, and the empty-budget render assertion. (covers: Chart-only change triggers the Helm job; Helm regression fails CI; Existing CI jobs and triggers are retained; Helm version is pinned; Default environment values are valid)
- [ ] 5.4 Confirm `.github/workflows/sdlc-checks.yml` is unchanged by the branch. (covers: Existing CI jobs and triggers are retained)

## 6. Dependency cleanup and follow-up

- [ ] 6.1 Remove `litellm` from `backend/pyproject.toml`, delete `backend/config.py`, regenerate `backend/poetry.lock` with `poetry -C backend lock`, and confirm the lock has no `litellm` package block and no module imports `litellm` or `backend.config`. (covers: litellm is absent; backend config module is removed; Lockfile is consistent; No module imports the removed dependency or config)
- [ ] 6.2 Keep `strands-agents` declared and record the wire-or-remove follow-up in the issue logbook and the PR body, citing the documentation and ADR-0001 that still claim it. (covers: strands-agents remains declared; Follow-up is recorded)

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
Expected: exit 0; resolver precedence cases pass; the 503 `detail` contains both
candidate paths and the `--manifest-path` build command; `/api/v1/health` stays
200 while the other endpoints return 503; `/policy/regime` leaves the effective
policy unchanged; `/risk/kill` leaves the kill switch active; `/chat` keeps the
applied regime.

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
docker run --rm --entrypoint sh robotrader:verify -c \
  'test -x /app/engine-rs/target/release/robotrader-node && test ! -e /app/engine-rs/target/debug/robotrader-node'
```
Expected: exit 0.

Controlled negative check for the stale-lock failure (restores the manifest
afterwards):

```bash
cp engine-rs/crates/node/Cargo.toml /tmp/robotrader-node-Cargo.toml.bak
printf '\nthiserror.workspace = true\n' >> engine-rs/crates/node/Cargo.toml
cargo build --release --locked --manifest-path engine-rs/Cargo.toml --bin robotrader-node
cp /tmp/robotrader-node-Cargo.toml.bak engine-rs/crates/node/Cargo.toml
```
Expected: the build exits non-zero with a lockfile-update error; the final `cp`
restores the committed manifest.

### Dependencies

```bash
grep -n 'litellm' backend/pyproject.toml
```
Expected: no match.

```bash
grep -n '^name = "litellm"$' backend/poetry.lock
```
Expected: no match.

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
```
Expected: both exit 0.

### CI wiring

```bash
grep -q 'charts/\*\*' .github/workflows/ci.yml
grep -q 'version: v4.2.3' .github/workflows/ci.yml
grep -q 'cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node' .github/workflows/ci.yml
```
Expected: all three exit 0.

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
