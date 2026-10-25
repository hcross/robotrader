# PLAN review — round 2 (closure)

**Change:** `align-asset-override-contract` · **Lane:** L · **Reviewed SHA:** `7e6ee05715aaf898f62bce8f1dfd3abbc92a032a`
**Reviewer:** `sdlc-plan-reviewer` (cold start) · **Stage:** `plan`

## Human summary

All eight R1 findings are closed at `7e6ee05`; no regression, security, or critical issue was introduced. F01's Docker packaging now copies `contracts/` to `/build/contracts` before `cargo build` and to `/app/contracts` in the runtime stage. F02's fixture is now live and, executed against the current binary, yields `total_trades = 0` / `rejected_orders = 7`, while the expired variant yields `4` / `3`, so the assertion proves the supplied envelope was used. F03–F08 are addressed. Traceability, strict-decode/parity, hot-path safety, rollback, and `## Verification` remain sound; `openspec validate --strict` and `sdlc.sh check` pass. Three non-blocking follow-ups are recorded for DEV: anchor the round-trip binary path to the repo root (CI runs tests from `backend/`), assert the exemption values against the real code defaults rather than the constant tuple, and enumerate the `PodAllocation`/top-level unknown-key scenarios in task 6.1.

## Findings

### PLAN-R1-F01 — blocker — closed — origin: initial

**Location:** `design.md#L60` (Impact), `design.md#L292-L298` (Migration), `tasks.md#L7` (task 1.5), `tasks.md#L70-L72` (Verification).

**Evidence:** The Impact table now lists `Dockerfile.backend` with both copies; Migration step 2 requires `COPY contracts` to `/build/contracts` before `cargo build` and to `/app/contracts` at runtime; task 1.5 repeats both and the bind-mount check; Verification adds `docker compose build backend`, an in-image `SAFE_BASELINE_TTL_SECONDS` import, and a packaged-binary policy run. The paths resolve correctly: `include_str!("../../../../contracts/policy_contract.conf")` from `/build/engine-rs/crates/common/src/lib.rs` is `/build/contracts`, and `parents[2]` from `/app/backend/core/schemas.py` is `/app/contracts`; `docker-compose.yml` mounts only `./backend:/app/backend`, and `.dockerignore` does not exclude `contracts`.

### PLAN-R1-F02 — blocker — closed — origin: initial

**Location:** `tasks.md#L46` (task 6.5), `tasks.md#L66` (Verification).

**Evidence:** Both now use `issued_at_ms = 1_792_180_000_000`, `ttl_seconds = 86_400`, empty `pod_allocations`, and assert `total_trades == 0` plus `rejected_orders > 0`, with the `base_ts` dependency documented. Empirically, the current binary run with that envelope returns `total_trades = 0`, `rejected_orders = 7` (the pods emit intents, but `HardRiskGate::validate` rejects every one with `PodDisabled` because the supplied allocation map is empty); the expired contrast (`issued_at_ms = 0`, `ttl_seconds = 900`) returns `total_trades = 4`, `rejected_orders = 3` via `safe_baseline`. The assertion therefore holds and distinguishes the supplied envelope from both the benchmark default and the safe baseline.

### PLAN-R1-F03 — minor — closed — origin: initial

**Location:** `design.md#L265` (bridge-count risk row), `tasks.md#L44` (task 6.3).

**Evidence:** The risk row now distinguishes the Rust fixtures (`None`) from the Python bridge (`default_active()` emitting `entry_obi_threshold = 0.08`, `max_rsi_long = 70.0`, `min_rsi_short = 30.0`, `take_profit_bps = 45.0`, `stop_loss_bps = 30.0`, and `None` USD zones), matching `backend/core/schemas.py#L20-L32`. Task 6.3 asserts those exact values before invoking Rust and keeps the preserve-or-rebaseline rule. The effective override OBI threshold is `0.08` in both paths, so the `6`/`1`/`4` bridge expectations remain coherent.

### PLAN-R1-F04 — minor — closed — origin: initial

**Location:** `tasks.md#L36` (task 5.2).

**Evidence:** The task now says "both **production** call sites (`#L573`, `#L642`)", places `min_rsi_short: float = 30.0` after `max_rsi_long`, propagates `rule.min_rsi_short if rule else 30.0`, and states that the two keyword-argument calls in `backend/tests/test_metrics_populations.py#L101,L112` intentionally use the `30.0` default. Verified: `compute_paper_execution_pnl` has `max_rsi_long: float = 68.0` followed by `venue`, so inserting `min_rsi_short` there leaves the keyword calls valid, and the two production sites are exactly `state_store.py#L573` and `#L642`.

### PLAN-R1-F05 — minor — closed — origin: initial

**Location:** `tasks.md#L3-L5` (tasks 1.1-1.3), `design.md#L201-L219`.

**Evidence:** Task 1.1 forbids repeating the assignment in the contract comment; task 1.2 specifies checker self-exclusion, `#`/`//` comment stripping, Python triple-quoted docstring stripping, the identifier-plus-numeric-literal predicate, and the explicit `EXEMPT_DEFAULTS` list; task 1.3 exercises a fixture with a bare `900` in `from_dict`/`default_active` plus a comment/docstring assignment and expects exit 0. The design defines the same predicate and exemptions. Residual (non-blocking follow-up, see summary): "assert both exemptions still equal `900`" can be satisfied by inspecting the static tuple instead of the real code defaults.

### PLAN-R1-F06 — minor — closed — origin: initial

**Location:** `tasks.md#L49` (task 6.8), `tasks.md#L68-L69` (Verification).

**Evidence:** Task 6.8 adds a repository guard against schema codegen dependencies, generated contract files, and a contract-emitting `build.rs`, with an allowlist for unrelated build scripts. Verification adds a `git diff --name-only master...HEAD` grep for generated/build artifacts and a manifest grep. I ran the manifest grep at the reviewed SHA: no match; `find . -name build.rs` returns nothing, so the guard is implementable without an allowlist entry today.

### PLAN-R1-F07 — minor — closed — origin: initial

**Location:** `tasks.md#L6` (task 1.4), `tasks.md#L45` (task 6.4), `design.md#L264`.

**Evidence:** Task 1.4 installs Rust with `Swatinem/rust-cache` in the Python job, runs `cargo build --bin robotrader-node` before the Python tests, and adds the path filters. Task 6.4 pins `engine-rs/target/debug/robotrader-node` and a `300 s` timeout for the `cargo run` fallback. The design risk row states the same. `.github/workflows/ci.yml#L36-L51` confirms the Python job currently has neither Rust setup nor a prebuild, so the added step is necessary and correctly placed. Residual (non-blocking follow-up): task 6.4 should anchor the path with `Path(__file__).resolve().parents[2]` because CI runs the suite with `working-directory: backend`.

### PLAN-R1-F08 — minor — closed — origin: initial

**Location:** `design.md#L170-L178` (gate semantics), `tasks.md#L43` (task 6.2).

**Evidence:** The design records the directional interpretation (`long OBI >= t`, `short OBI <= -t`) as a strengthening of the SPEC magnitude condition, explains why `|OBI| >= t` remains necessary in both branches, and states no spec clarification is escalated because every approved scenario holds. Task 6.2 now names the sign-asymmetry cases: a long with `OBI == -t` and a short with `OBI == +t` must emit no intent. This is a named verification of the interpretation, not a spec change; `specs/contract/spec.md#L103` still states `|OBI| >= entry_obi_threshold` for both directions, which the directional rule implies.

## Checklist walk (closure)

| Checklist item | Result | Evidence |
|---|---|---|
| Traceability: requirement -> task | PASS | Requirements 1-8 map to groups 2-6; no unapproved behaviour added. |
| Decisions name alternatives / rejections | PASS | D1-D14 unchanged by the revision; D6/D9/D11-D13 still cite rejected alternatives. |
| Contract parity and strict decode | PASS | `design.md#L114-L140`; `tasks.md#L11-L16`; PodAllocation's five keys and the six top-level keys match the Python serializer. |
| Hot path / 50 µs | PASS | No allocation, logging, or I/O added; TTL is a `const fn` compile-time constant. |
| Capital / vault / chain isolation | PASS | Untouched; no allocation or key path changed. |
| Test strategy / scenario coverage | PASS | Tasks 6.1-6.8 plus Verification cover every requirement; F06's gap is closed. |
| Rollback concrete | PASS | `design.md#L305-L320`; revert-and-rebuild with no data repair. |
| Tasks checkbox / dependency order | PASS | 35 tasks under 7 numbered groups; order is 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 with no cycle. |
| `## Verification` executable from root | PASS | Commands are root-runnable; Docker commands assume the standard local `.env` (absent in this worktree, pre-existing repo precondition). |
| No hidden spec change | PASS | The only narrowing (directional OBI) is recorded and tested, not patched into the spec. |

## Checks run

| Command / inspection | Result |
|---|---|
| `git rev-parse HEAD` | `7e6ee05715aaf898f62bce8f1dfd3abbc92a032a` |
| Working-tree artifact hashes vs `git show HEAD:` | `design.md` and `tasks.md` identical to HEAD; only `.sdlc/.../state.json` and the R2 brief are dirty |
| `openspec validate align-asset-override-contract --strict` | `Change 'align-asset-override-contract' is valid` (exit 0) |
| `scripts/sdlc/sdlc.sh check align-asset-override-contract` | `check: PASS` (exit 0); `spec-r2 APPROVE`, `plan-r1 CHANGES_REQUESTED` |
| `cargo build --bin robotrader-node` | exit 0 |
| `robotrader-node --policy-json '{"envelope_id":"x","issued_at_ms":1792180000000,"ttl_seconds":86400,"global_regime":"LOW_VOL_CARRY","pod_allocations":{},"asset_overrides":{}}'` | exit 0; `total_trades = 0`, `rejected_orders = 7` (F02 fixture) |
| Same CLI with `issued_at_ms = 0`, `ttl_seconds = 900` | `total_trades = 4`, `rejected_orders = 3` (safe-baseline contrast) |
| `grep -RInE 'schemars|progenitor|datamodel-codegen|json-schema|codegen' engine-rs/crates/*/Cargo.toml backend/pyproject.toml` | no match (exit 1), as F06's Verification expects |
| `find . -name build.rs` (excluding `target`) | no output |
| Read `Dockerfile.backend`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/ci.yml` | confirmed F01/F07 paths, bind mount, context, and missing Python-job Rust setup |
| Read `engine-rs/crates/common/src/lib.rs`, `risk-gate/src/lib.rs`, `strategies/src/lib.rs`, `backtest/src/lib.rs`, `node/src/main.rs` | confirmed pod emission, `PodDisabled` gate filter, `effective()` fallback, and `base_ts` |
| Read `backend/core/schemas.py`, `backend/core/state_store.py`, `backend/tests/test_architecture.py`, `backend/tests/test_metrics_populations.py` | confirmed Python defaults, call sites, and bridge test |
| Read approved SPEC (`specs/contract/spec.md`) at the SPEC-approved content | all requirements covered; no spec gap |

## Verdict

`APPROVE` — 0 open blocker, 0 open major, 0 open minor, 0 new findings. All eight R1 findings are closed at `7e6ee05`. The plan may proceed to DEV.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "plan",
  "round": 2,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "7e6ee05715aaf898f62bce8f1dfd3abbc92a032a",
  "verdict": "APPROVE",
  "summary": "All eight R1 plan findings are closed at 7e6ee05 with executable evidence, and no regression, security, or critical finding was introduced.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/design.md#L60; design.md#L292-L298; tasks.md#L7; tasks.md#L70-L72",
      "evidence": "Impact lists Dockerfile.backend; Migration and task 1.5 copy contracts/ to /build/contracts before cargo build and to /app/contracts at runtime; Verification adds build, in-image import, and packaged-binary checks. The include_str! and parents[2] paths resolve to those locations; .dockerignore does not exclude contracts and the compose mount only shadows /app/backend.",
      "required_fix": "None; fix verified."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L46; tasks.md#L66",
      "evidence": "Task 6.5 and Verification use issued_at_ms = 1792180000000, ttl_seconds = 86400, empty pod_allocations, and assert total_trades == 0 plus rejected_orders > 0. Running the current binary with that envelope returns 0 trades and 7 rejections; the expired variant returns 4 trades and 3 rejections via safe_baseline, so the assertion distinguishes the supplied envelope.",
      "required_fix": "None; fix verified empirically."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/design.md#L265; tasks.md#L44",
      "evidence": "The risk row distinguishes Rust None fixtures from Python default_active() defaults and task 6.3 asserts entry_obi_threshold 0.08, max_rsi_long 70.0, min_rsi_short 30.0, take_profit_bps 45.0, stop_loss_bps 30.0, and None USD zones before invoking Rust.",
      "required_fix": "None; fix verified."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L36",
      "evidence": "Task 5.2 scopes the change to the two production call sites (state_store.py#L573, #L642), places min_rsi_short after max_rsi_long, and states that the two keyword-argument test calls intentionally use the 30.0 default. The signature confirms the placement is valid.",
      "required_fix": "None; fix verified."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L3-L5; design.md#L201-L219",
      "evidence": "Task 1.1 forbids repeating the assignment in the contract comment; task 1.2 adds self-exclusion, comment/docstring stripping, the numeric-declaration predicate, and EXEMPT_DEFAULTS; task 1.3 exercises a bare-900 fixture with a comment/docstring assignment and expects exit 0. The design defines the same predicate and exemptions.",
      "required_fix": "None; fix verified. Non-blocking follow-up: assert the exemption values against the real code defaults rather than the constant tuple."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L49; tasks.md#L68-L69",
      "evidence": "Task 6.8 adds a repository guard against codegen dependencies, generated contract files, and a contract-emitting build.rs; Verification greps the manifests and the diff. The manifest grep returns no match and no build.rs exists at the reviewed SHA.",
      "required_fix": "None; fix verified."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L6; tasks.md#L45; design.md#L264",
      "evidence": "Task 1.4 installs Rust with Swatinem/rust-cache and prebuilds cargo build --bin robotrader-node in the Python job; task 6.4 pins engine-rs/target/debug/robotrader-node and a 300 s fallback timeout; the design risk row states the same. ci.yml confirms the Python job currently lacks Rust setup.",
      "required_fix": "None; fix verified. Non-blocking follow-up: anchor the binary path to the repo root because CI runs tests from backend/."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/design.md#L170-L178; tasks.md#L43",
      "evidence": "The design records the directional OBI interpretation as a strengthening of the SPEC magnitude condition and task 6.2 names the sign-asymmetry cases (long OBI == -t and short OBI == +t emit no intent). All approved scenarios remain satisfied and no spec clarification is required.",
      "required_fix": "None; fix verified."
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
    "PLAN-R1-F08"
  ]
}
```
