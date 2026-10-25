# build-packaging Specification

## Purpose
TBD - created by archiving change harden-build-packaging. Update Purpose after archive.
## Requirements
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

### Requirement: Helm chart exposes service, ingress, and runtime environment

The rendered Service MUST use `.Values.service.type` and `.Values.service.port`, MUST target container port 8000, and MUST select the same labels as the Deployment pods. When `.Values.ingress.enabled` is true, the chart MUST render an Ingress that routes to the Service and honours a configurable host and path. The Deployment MUST expose `REDIS_URL` and `MAX_DAILY_LLM_BUDGET_USD` with values driven by chart values, and MUST preserve `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`.

`values.yaml` MUST declare and document `env.redisUrl` with the default empty string (selecting the backend's in-memory fallback) and `env.maxDailyLlmBudgetUsd` with the default `5.0`. The chart MUST render a non-empty numeric `MAX_DAILY_LLM_BUDGET_USD` even when the configured value is an empty string, so the backend never parses an empty budget.

#### Scenario: Service matches the deployment pods

- **WHEN** `helm template charts/robotrader` renders the default release
- **THEN** the Service `spec.selector` equals the Deployment pod labels
- **THEN** the Service exposes `.Values.service.port` and targets port 8000

#### Scenario: Ingress renders when enabled

- **WHEN** `helm template charts/robotrader --set ingress.enabled=true --set ingress.host=robotrader.example.test --set ingress.path=/` runs
- **THEN** the output contains an `Ingress` whose backend references the chart's Service and the configured host and path

#### Scenario: No Ingress when disabled

- **WHEN** `helm template charts/robotrader` runs with the default `ingress.enabled=false`
- **THEN** the output contains no `Ingress`

#### Scenario: Default environment values are valid

- **WHEN** `helm template charts/robotrader` runs with the default `values.yaml`
- **THEN** `values.yaml` declares and documents `env.redisUrl` and `env.maxDailyLlmBudgetUsd`
- **THEN** the Deployment contains `REDIS_URL` whose value is empty or a valid URL
- **THEN** the Deployment contains `MAX_DAILY_LLM_BUDGET_USD` whose value parses as a positive floating-point number
- **THEN** the Deployment still contains `OPENROUTER_API_KEY` and `SOLANA_RPC_URL`

#### Scenario: Explicit environment overrides are rendered

- **WHEN** `helm template charts/robotrader --set env.redisUrl=redis://cache:6379/0 --set env.maxDailyLlmBudgetUsd=7.5` runs
- **THEN** the Deployment contains `REDIS_URL` with value `redis://cache:6379/0`
- **THEN** the Deployment contains `MAX_DAILY_LLM_BUDGET_USD` with value `7.5`

#### Scenario: Empty budget override falls back to a valid number

- **WHEN** `helm template charts/robotrader --set env.maxDailyLlmBudgetUsd=""` runs
- **THEN** the rendered `MAX_DAILY_LLM_BUDGET_USD` is `5.0`
- **THEN** the rendered value parses as a positive floating-point number

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

### Requirement: Container installs the release binary at the release path

The built image MUST contain the `robotrader-node` binary at `/app/engine-rs/target/release/robotrader-node` and MUST NOT contain a copy at `/app/engine-rs/target/debug/robotrader-node`.

#### Scenario: Release binary is installed

- **WHEN** the image is built
- **THEN** `/app/engine-rs/target/release/robotrader-node` exists and is executable
- **THEN** `/app/engine-rs/target/debug/robotrader-node` does not exist

### Requirement: Python package markers and documented test discovery

`backend/__init__.py` and `backend/tests/__init__.py` MUST exist. With the backend dependencies installed and a `robotrader-node` binary provisioned as required by the CI-provisioning requirement, `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` MUST exit 0 and MUST execute every `test_*.py` module under `backend/tests`.

#### Scenario: Markers exist

- **WHEN** the repository tree is inspected
- **THEN** `backend/__init__.py` exists
- **THEN** `backend/tests/__init__.py` exists

#### Scenario: Discovery loads every test module

- **WHEN** `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` runs from the repository root with the backend dependencies installed and the `robotrader-node` binary provisioned
- **THEN** the command exits 0
- **THEN** every `test_*.py` module under `backend/tests` is loaded

#### Scenario: Discovery is stable across supported Python versions

- **WHEN** the documented command runs on a Python version supported by `backend/pyproject.toml`
- **THEN** the command exits 0
- **THEN** the loader reports no `Start directory is not importable` error

### Requirement: CI provisions the Rust binary for the Python suite

The Python CI job MUST install the Rust toolchain and MUST build `robotrader-node` before running the Python suite. The build MUST be runnable from the repository root as `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node`. The documented local test procedure in `README.md` and `AGENTS.md` MUST include the build step before `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v`.

#### Scenario: Python CI job builds the binary before the suite

- **WHEN** `.github/workflows/ci.yml` runs the Python job on a clean checkout with no `engine-rs/target/`
- **THEN** the job installs the Rust toolchain
- **THEN** the `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` step completes before the Python discovery step
- **THEN** the Python discovery step exits 0

#### Scenario: Documented local procedure includes the build step

- **WHEN** a reader follows `README.md` or `AGENTS.md` from a clean checkout with no prebuilt binary
- **THEN** the documented procedure builds `robotrader-node` before running the discovery command
- **THEN** the discovery command exits 0

### Requirement: One shared Rust binary resolver without a compiler fallback

`run_rust_backtest` and `run_rust_backtest_for_leaf` MUST obtain the `robotrader-node` path from one shared resolver for the backtest methods. The resolver MUST use debug-first precedence: `engine-rs/target/debug/robotrader-node` when present, otherwise `engine-rs/target/release/robotrader-node`. It MUST NOT invoke `cargo`, `rustc`, or any other compiler. A missing binary MUST raise a typed, actionable error rather than fall back to a compiler. The separate vault-manifest/sign-transfer candidate list in `backend/core/hierarchy.py` is out of scope and MUST remain unchanged.

#### Scenario: Both methods use the selected binary

- **WHEN** only `engine-rs/target/release/robotrader-node` exists and both `run_rust_backtest` and `run_rust_backtest_for_leaf` are called
- **THEN** both methods invoke the binary at `engine-rs/target/release/robotrader-node`
- **THEN** each method returns its normal result shape

#### Scenario: Debug build is used when present

- **WHEN** only `engine-rs/target/debug/robotrader-node` exists
- **THEN** the resolver selects the debug path

#### Scenario: Fresh debug build wins over release

- **WHEN** both `engine-rs/target/debug/robotrader-node` and `engine-rs/target/release/robotrader-node` exist
- **THEN** the resolver selects the debug path
- **THEN** a fresh local debug build is not shadowed by a stale release build

#### Scenario: Release is used as the fallback

- **WHEN** only `engine-rs/target/release/robotrader-node` exists
- **THEN** the resolver selects the release path
- **THEN** the container, which has no debug binary, resolves the release binary

#### Scenario: No compiler is invoked

- **WHEN** no binary exists and `run_rust_backtest` is called
- **THEN** no `cargo run`, `cargo build`, or other compiler process is spawned
- **THEN** the resolver raises the typed missing-binary error

### Requirement: Actionable missing-binary error on backtest-dependent endpoints

The backend MUST map the typed missing-binary error through one global exception handler so that every HTTP endpoint that invokes `run_rust_backtest` or `run_rust_backtest_for_leaf` returns HTTP 503 with `application/json` and a uniform `detail` string. The `detail` MUST contain both candidate paths (`engine-rs/target/release/robotrader-node` and `engine-rs/target/debug/robotrader-node`) and the exact build command `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node`, which is runnable from the repository root. `GET /api/v1/health` MUST continue to return HTTP 200 and MUST NOT depend on the binary.

The affected endpoints and their state side effects are:

| Endpoint | Resolver invocation | State side effect on a missing binary |
|---|---|---|
| `GET /api/v1/status` | `run_rust_backtest` | none |
| `GET /api/v1/hierarchy` | `run_rust_backtest` | none |
| `POST /api/v1/backtest/run` | `run_rust_backtest` | none |
| `POST /api/v1/leaf/{leaf_id}/backtest` | `run_rust_backtest_for_leaf` | none |
| `POST /api/v1/policy/regime` | `run_rust_backtest` | none: the preset MUST NOT be applied |
| `POST /api/v1/risk/kill` | `run_rust_backtest` | the kill-switch mutation MUST be applied |
| `POST /api/v1/chat` | transitive via `process_user_command` | a regime change already applied MUST remain applied |

#### Scenario: Read endpoints return the uniform 503

- **WHEN** no `robotrader-node` binary exists and a client sends `GET /api/v1/status` and `GET /api/v1/hierarchy`
- **THEN** each response has HTTP status 503 and content type `application/json`
- **THEN** each `detail` satisfies the uniform detail contract defined in this requirement

#### Scenario: Leaf backtest returns the uniform 503

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/leaf/{leaf_id}/backtest`
- **THEN** the response has HTTP status 503 and content type `application/json`
- **THEN** `detail` satisfies the uniform detail contract defined in this requirement

#### Scenario: Backtest mutation endpoint returns the uniform 503

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/backtest/run`
- **THEN** the response has HTTP status 503 and content type `application/json`
- **THEN** `detail` satisfies the uniform detail contract defined in this requirement
- **THEN** no backtest summary is returned

#### Scenario: Policy regime does not apply on a missing binary

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/policy/regime` with a preset
- **THEN** the response has HTTP status 503 with the uniform detail contract
- **THEN** the state store's effective policy remains the pre-request envelope

#### Scenario: Kill switch applies despite the missing binary

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/risk/kill` with `active=true`
- **THEN** the response has HTTP status 503 with the uniform detail contract
- **THEN** the state store's kill switch is active after the request

#### Scenario: Chat commands return the uniform 503

- **WHEN** no `robotrader-node` binary exists and a client sends `POST /api/v1/chat` with a command that invokes the resolver
- **THEN** the response has HTTP status 503 with the uniform detail contract
- **THEN** a regime change already applied by the command remains applied

#### Scenario: Health and process survive a missing binary

- **WHEN** the backend starts without a `robotrader-node` binary
- **THEN** the process remains running and `GET /api/v1/health` returns HTTP 200 with `status` equal to `ok`
- **THEN** no compiler process is spawned by the health request

### Requirement: CI gates Helm chart changes

CI MUST run `helm lint charts/robotrader` and `helm template charts/robotrader`. The workflow MUST include `charts/**` in the `pull_request.paths` and `push.paths` filters of `.github/workflows/ci.yml`, and MUST install a pinned Helm version. The existing Rust, Python, and frontend jobs in `ci.yml` MUST remain. The SDLC workflow in `.github/workflows/sdlc-checks.yml` is out of scope and MUST remain unchanged.

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

#### Scenario: No module imports the removed dependency or config

- **WHEN** the backend source tree is searched for `import litellm` and `backend.config`
- **THEN** no module matches
- **THEN** the test suite still exits 0 under the build-then-test procedure

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

