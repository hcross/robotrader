## ADDED Requirements

### Requirement: Helm chart renders with default values

`helm template charts/robotrader` MUST exit 0 with the chart's default values and MUST render a Deployment and a Service. The chart MUST define the helpers `robotrader.fullname`, `robotrader.labels`, and `robotrader.selectorLabels` so no template references a missing definition. `helm lint charts/robotrader` MUST exit 0.

#### Scenario: Default render succeeds

- **WHEN** `helm template charts/robotrader` runs from the repository root with the default `values.yaml`
- **THEN** the command exits 0
- **THEN** the rendered output contains one `Deployment` and one `Service` for the chart

#### Scenario: Lint succeeds

- **WHEN** `helm lint charts/robotrader` runs from the repository root
- **THEN** the command exits 0
- **THEN** the output contains no `[ERROR]` line

#### Scenario: No missing template definition

- **WHEN** any chart template includes `robotrader.fullname`, `robotrader.labels`, or `robotrader.selectorLabels`
- **THEN** the render resolves each include and exits 0
- **THEN** the output contains no `no template` error

### Requirement: Helm chart exposes service, ingress, and runtime environment

The rendered Service MUST use `.Values.service.type` and `.Values.service.port`, MUST target container port 8000, and MUST select the same labels as the Deployment pods. When `.Values.ingress.enabled` is true, the chart MUST render an Ingress that routes to the Service and honours a configurable host and path. The Deployment MUST expose `REDIS_URL` and `MAX_DAILY_LLM_BUDGET_USD` with values driven by chart values, and MUST preserve `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`.

#### Scenario: Service matches the deployment pods

- **WHEN** `helm template charts/robotrader` renders the default release
- **THEN** the Service `spec.selector` equals the Deployment pod labels
- **THEN** the Service exposes `.Values.service.port` and targets port 8000

#### Scenario: Ingress renders only when enabled

- **WHEN** `helm template charts/robotrader --set ingress.enabled=true --set ingress.host=robotrader.example.test --set ingress.path=/` runs
- **THEN** the output contains an `Ingress` whose backend references the chart's Service and the configured host and path
- **WHEN** `helm template charts/robotrader` runs with `ingress.enabled=false`
- **THEN** the output contains no `Ingress`

#### Scenario: Redis and LLM budget environment is present

- **WHEN** `helm template charts/robotrader --set env.redisUrl=redis://cache:6379/0 --set env.maxDailyLlmBudgetUsd=7.5` runs
- **THEN** the Deployment contains `REDIS_URL` with value `redis://cache:6379/0`
- **THEN** the Deployment contains `MAX_DAILY_LLM_BUDGET_USD` with value `7.5`
- **THEN** the Deployment still contains `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`

### Requirement: Docker build consumes the committed lockfile

The Docker build context MUST include `engine-rs/Cargo.lock`, and `Dockerfile.backend` MUST copy that lockfile before building the Rust workspace. The Rust build MUST run in locked mode so a lockfile inconsistent with `engine-rs/Cargo.toml` fails the build instead of resolving new versions.

#### Scenario: Lockfile is in the build context

- **WHEN** the image is built from the repository root
- **THEN** `.dockerignore` does not exclude `engine-rs/Cargo.lock`
- **THEN** the Rust builder stage receives `engine-rs/Cargo.lock` before `cargo build`

#### Scenario: Inconsistent lockfile fails the build

- **WHEN** `engine-rs/Cargo.toml` is modified without regenerating `engine-rs/Cargo.lock` and the image is built
- **THEN** the Rust builder stage exits non-zero with a lockfile error
- **THEN** the build does not silently resolve a different dependency version

#### Scenario: Build uses the committed dependency versions

- **WHEN** the image is built from an unmodified checkout
- **THEN** the Rust builder stage succeeds in locked mode
- **THEN** the resolved dependency versions match `engine-rs/Cargo.lock`

### Requirement: Container installs the release binary at the release path

The built image MUST contain the `robotrader-node` binary at `/app/engine-rs/target/release/robotrader-node` and MUST NOT contain a copy at `/app/engine-rs/target/debug/robotrader-node`.

#### Scenario: Release binary is installed

- **WHEN** the image is built
- **THEN** `/app/engine-rs/target/release/robotrader-node` exists and is executable
- **THEN** `/app/engine-rs/target/debug/robotrader-node` does not exist

#### Scenario: Container request path uses the release build

- **WHEN** `/api/v1/status` is served from the image and the Rust binary is present
- **THEN** the backend executes `/app/engine-rs/target/release/robotrader-node`
- **THEN** the response is HTTP 200

### Requirement: Python package markers and documented test discovery

`backend/__init__.py` and `backend/tests/__init__.py` MUST exist. With the backend dependencies installed, `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` MUST exit 0 and MUST execute every `test_*.py` module under `backend/tests`.

#### Scenario: Markers exist

- **WHEN** the repository tree is inspected
- **THEN** `backend/__init__.py` exists
- **THEN** `backend/tests/__init__.py` exists

#### Scenario: Documented discovery command passes

- **WHEN** `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` runs from the repository root with the backend dependencies installed
- **THEN** the command exits 0
- **THEN** every `test_*.py` module under `backend/tests` is loaded

#### Scenario: Discovery does not depend on namespace packages

- **WHEN** the documented command runs on a Python version supported by `backend/pyproject.toml`
- **THEN** the loader does not report `Start directory is not importable`
- **THEN** the package markers, not namespace-package behaviour, make the start directory importable

### Requirement: One Rust binary resolver without a compiler fallback

`run_rust_backtest` and `run_rust_backtest_for_leaf` MUST obtain the `robotrader-node` path from one shared resolver. The resolver MUST prefer `engine-rs/target/release/robotrader-node` when present, otherwise use `engine-rs/target/debug/robotrader-node` when present, and MUST NOT invoke `cargo`, `rustc`, or any other compiler. A missing binary MUST raise a typed, actionable error rather than fall back to a compiler.

#### Scenario: Both methods use the same resolver

- **WHEN** only `engine-rs/target/release/robotrader-node` exists
- **THEN** both `run_rust_backtest` and `run_rust_backtest_for_leaf` execute that release binary
- **THEN** neither method constructs its own binary path

#### Scenario: Release build is preferred

- **WHEN** both `engine-rs/target/release/robotrader-node` and `engine-rs/target/debug/robotrader-node` exist
- **THEN** the resolver returns the release path

#### Scenario: Local debug build is usable

- **WHEN** only `engine-rs/target/debug/robotrader-node` exists
- **THEN** the resolver returns the debug path

#### Scenario: No compiler is invoked

- **WHEN** no binary exists and `run_rust_backtest` is called
- **THEN** no `cargo run`, `cargo build`, or other compiler process is spawned
- **THEN** the resolver raises the typed missing-binary error

### Requirement: Actionable missing-binary error on backtest-dependent endpoints

When the Rust binary is missing, every HTTP endpoint that invokes `run_rust_backtest` or `run_rust_backtest_for_leaf` MUST return HTTP 503 with `application/json` and a `detail` string that names the expected release path and the command that builds the binary. The response MUST NOT be a bare generic 500. `GET /api/v1/health` MUST continue to return HTTP 200 and MUST NOT depend on the binary.

#### Scenario: Status returns 503 with an actionable detail

- **WHEN** no `robotrader-node` binary exists and a client sends `GET /api/v1/status`
- **THEN** the response has HTTP status 503 and content type `application/json`
- **THEN** `detail` contains `engine-rs/target/release/robotrader-node`
- **THEN** `detail` contains `cargo build --release --bin robotrader-node`

#### Scenario: Leaf backtest returns the same failure shape

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/leaf/{leaf_id}/backtest`
- **THEN** the response has HTTP status 503 and content type `application/json`
- **THEN** `detail` follows the same path-and-build-command contract as the status endpoint

#### Scenario: Health is independent of the binary

- **WHEN** no `robotrader-node` binary exists and a client sends `GET /api/v1/health`
- **THEN** the response is HTTP 200 with `status` equal to `ok`
- **THEN** no compiler process is spawned by the health request

#### Scenario: Backend stays up without the binary

- **WHEN** the backend starts without a `robotrader-node` binary
- **THEN** the process remains running and the health endpoint responds
- **THEN** backtest-dependent endpoints return the 503 contract

### Requirement: CI gates Helm chart changes

CI MUST run `helm lint charts/robotrader` and `helm template charts/robotrader`. The workflow MUST include `charts/**` in the `pull_request.paths` and `push.paths` filters, and MUST install a pinned Helm version. The existing Rust, Python, frontend, and SDLC jobs MUST remain.

#### Scenario: Chart-only change triggers the Helm job

- **WHEN** a pull request changes only a file under `charts/`
- **THEN** the CI workflow is triggered
- **THEN** the Helm job runs `helm lint charts/robotrader` and `helm template charts/robotrader`

#### Scenario: Helm regression fails CI

- **WHEN** a chart change reintroduces a missing helper or invalid template
- **THEN** `helm lint` or `helm template` exits non-zero
- **THEN** the CI job fails

#### Scenario: Existing CI jobs and triggers are retained

- **WHEN** a pull request changes a file under `engine-rs/`, `backend/`, or `frontend/`
- **THEN** the existing Rust, Python, and frontend jobs still run
- **THEN** the existing path filters for those directories remain in place

#### Scenario: Helm version is pinned

- **WHEN** the CI workflow is inspected
- **THEN** the Helm installation step names an explicit Helm version
- **THEN** the workflow does not install an unpinned latest release

### Requirement: Unused litellm dependency and backend config are removed

`backend/pyproject.toml` MUST NOT declare `litellm`, and `backend/config.py` MUST be removed because no module imports it. `backend/poetry.lock` MUST be regenerated so a clean `poetry install --no-root` succeeds without a stale-lock error. The removal MUST NOT change backend runtime behaviour.

#### Scenario: litellm is absent

- **WHEN** `backend/pyproject.toml` and `backend/poetry.lock` are inspected
- **THEN** neither file declares `litellm`
- **THEN** no Python module imports `litellm`

#### Scenario: backend config module is removed

- **WHEN** the repository tree is inspected
- **THEN** `backend/config.py` does not exist
- **THEN** no Python module imports `backend.config`

#### Scenario: Lockfile is consistent

- **WHEN** a clean environment runs `poetry install --no-root` in `backend/`
- **THEN** the command succeeds without a stale-lock error
- **THEN** the installed dependency set matches `backend/poetry.lock`

#### Scenario: Backend behaviour is unchanged

- **WHEN** `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` runs after the removal
- **THEN** the suite still exits 0
- **THEN** no backend module imports `litellm` or `backend.config`

### Requirement: strands-agents is retained with a recorded follow-up

`strands-agents` MUST remain declared in `backend/pyproject.toml` and `backend/poetry.lock` because the repository documentation and ADR-0001 still describe it as the intended warm-path LLM library. The change MUST record an explicit follow-up to wire it in or remove it.

#### Scenario: strands-agents remains declared

- **WHEN** `backend/pyproject.toml` and `backend/poetry.lock` are inspected
- **THEN** `strands-agents` is still declared
- **THEN** the change does not silently drop it

#### Scenario: Follow-up is recorded

- **WHEN** the issue logbook or pull-request body is inspected
- **THEN** a follow-up entry states that `strands-agents` must be wired in or removed
- **THEN** the follow-up references the documentation or ADR that still claims it
