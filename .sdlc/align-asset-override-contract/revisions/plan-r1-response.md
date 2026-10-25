stage: plan
round: 1
head_sha: 10721e65e160c4ed8c057a06f81fa89d36e3226d
responses:
  - id: PLAN-R1-F01
    action: fixed
    evidence: "Added the Docker packaging decision to the Impact table (`Dockerfile.backend` row) and to the Migration Plan deployment step: builder `COPY contracts /build/contracts` before `cargo build`, runtime `COPY contracts ./contracts`, with a note that `./backend:/app/backend` does not shadow `/app/contracts`. Added task 1.5 for both Dockerfile stages and three Verification commands: `docker compose build backend`, a runtime import of `SAFE_BASELINE_TTL_SECONDS` inside the image, and the packaged binary policy run."
  - id: PLAN-R1-F02
    action: fixed
    evidence: "Task 6.5 and the valid-policy Verification command now use `issued_at_ms = 1_792_180_000_000` (matching `base_ts` in `engine-rs/crates/backtest/src/lib.rs`) with `ttl_seconds = 86_400`, and assert `total_trades == 0` plus `rejected_orders > 0`; the empty `pod_allocations` envelope would produce trades under `safe_baseline`, so the assertions prove the supplied envelope was used. Task 6.5 documents the `base_ts` dependency."
  - id: PLAN-R1-F03
    action: fixed
    evidence: "Corrected the bridge-counter Risk row in `design.md`: the four Rust fixtures use `None`, while the Python bridge (`PolicyEnvelope.default_active()`) emits explicit defaults (`0.08`, `70.0`, `30.0`, `45.0`, `30.0`, and `None` USD zones). Task 6.3 now asserts those exact Python defaults in `test_python_to_rust_backtest_bridge_and_regime_switching` before invoking Rust, and keeps the preserve-or-rebaseline rule."
  - id: PLAN-R1-F04
    action: fixed
    evidence: "Task 5.2 now says `min_rsi_short: float = 30.0` is added after `max_rsi_long`, propagates `rule.min_rsi_short if rule else 30.0` at the two production call sites (`state_store.py#L573`, `#L642`), and states that the two keyword-argument test calls in `backend/tests/test_metrics_populations.py` intentionally use the `30.0` default."
  - id: PLAN-R1-F05
    action: fixed
    evidence: "Task 1.1 forbids repeating the assignment in the contract comment. Task 1.2 adds checker self-exclusion, `#`/`//` comment stripping, Python triple-quoted docstring stripping, and an explicit `EXEMPT_DEFAULTS` list for `schemas.py::from_dict` and `::default_active`. The design now defines the same predicate and lists the exemptions; task 1.3 and its Verification command exercise a fixture with a bare `900` in both exempted functions and a comment/docstring assignment, asserting exit 0, and assert both exemptions still equal `900`."
  - id: PLAN-R1-F06
    action: fixed
    evidence: "Added task 6.8 for a repository guard against schema codegen dependencies, generated contract files, and contract-emitting `build.rs`, plus two Verification commands: a `git diff --name-only master...HEAD` grep for generated/build artifacts and a grep for codegen dependencies in the Cargo and Poetry manifests. Both expect no output/match."
  - id: PLAN-R1-F07
    action: fixed
    evidence: "Task 1.4 now installs Rust with `Swatinem/rust-cache` and runs `cargo build --bin robotrader-node` before the Python tests. Task 6.4 pins the expected binary path `engine-rs/target/debug/robotrader-node` and a 300 s timeout for the `cargo run` fallback. The design Risk row is updated accordingly."
  - id: PLAN-R1-F08
    action: fixed
    evidence: "The design gate-semantics section records the directional interpretation (`long OBI >= t`, `short OBI <= -t`) as a strengthening of the SPEC magnitude condition and states that no spec clarification is escalated because every approved scenario holds. Task 6.2 now requires named sign-asymmetry cases: a long with `OBI == -t` and a short with `OBI == +t` must emit no intent."
