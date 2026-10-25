# PLAN review — round 1

**Change:** `align-asset-override-contract` · **Lane:** L · **Reviewed SHA:** `10721e65e160c4ed8c057a06f81fa89d36e3226d`
**Reviewer:** `sdlc-plan-reviewer` (cold start) · **Stage:** `plan`

## Human summary

The plan is materially sound but not approvable. Two blockers: (1) `contracts/policy_contract.conf` is absent from both Docker stages, so `include_str!` and the Python import break the mandatory `docker compose up --build -d` gate; (2) the valid-policy verification uses `issued_at_ms: 0`, which is expired against the 2026 fixture timestamps and falls back to `safe_baseline`, so its expected `total_trades == 0` is false. Six minors cover the TTL checker's self-scan/exemption precision, the CI Rust build timeout, the bridge-counter premise (Rust fixtures use `None`, Python emits defaults), the `compute_paper_execution_pnl` call-site count, the missing "no codegen" verification, and the directional OBI/spec wording. Traceability, contract parity, hot-path safety, and rollback are otherwise complete.

## Findings

### PLAN-R1-F01 — blocker — open — origin: initial

**Location:** `openspec/changes/align-asset-override-contract/design.md#L48-L60` (Impact table) and `#L188-L195`; `tasks.md` groups 1 and 7; `Verification` `#L67`; `Dockerfile.backend#L1-L26`.

**Evidence:** The design sources the TTL through `include_str!("../../../../contracts/policy_contract.conf")` from `engine-rs/crates/common/src/lib.rs` and the Python module through `contracts/policy_contract.conf`. `Dockerfile.backend`'s builder stage (`WORKDIR /build/engine-rs`) copies only `engine-rs/Cargo.toml` and `engine-rs/crates`, so the include path resolves to `/build/contracts/policy_contract.conf`, which is never copied; that stage fails at `cargo build`. The runtime stage copies only `backend ./backend`, so `backend/core/schemas.py` resolving `Path(__file__).resolve().parents[2] / "contracts"` points at `/app/contracts/policy_contract.conf`, which is absent; `import backend.core.schemas` then fails under `uvicorn`. `ls contracts` shows the directory does not exist yet. The Impact table omits `Dockerfile.backend`, and the plan's `docker compose up --build -d` verification (`tasks.md#L67`) cannot pass.

**Required fix:** Add a task (group 1 or 7) that copies `contracts/` into the builder at the path `include_str!` resolves to (`/build/contracts/...`, or adjust the include path) and into the runtime image at `/app/contracts`; update the Impact table to list `Dockerfile.backend`; add a Verification step that builds the image and imports `backend.core.schemas` (and runs the binary) inside it. Confirm the `./backend:/app/backend` compose volume does not hide the runtime contract file.

---

### PLAN-R1-F02 — blocker — open — origin: initial

**Location:** `tasks.md#L45` (task 6.5) and `tasks.md#L63` (valid-policy Verification command).

**Evidence:** Both use `"issued_at_ms":0,"ttl_seconds":900`. The benchmark events are stamped at `base_ts = 1_792_180_000_000` (`engine-rs/crates/backtest/src/lib.rs#L157`). `HardRiskGate::validate` resolves `raw_envelope.effective(now_ms)` (`engine-rs/crates/risk-gate/src/lib.rs#L240`), and `is_expired` is `now_ms > issued_at_ms + ttl_seconds*1000` (`engine-rs/crates/common/src/lib.rs#L177-L179`); `1.79e12 > 900_000`, so the supplied envelope is discarded. `safe_baseline` then enables `pod_carry` (weight 0.50) and `pod_momentum` (0.25) (`common/src/lib.rs#L182-L223`), and the benchmark's funding/OBI values satisfy both pods, so `total_trades == 0` is false. The test would fail; even if the count happened to be 0, it would prove the fallback, not that the supplied envelope was used.

**Required fix:** In both task 6.5 and the Verification command, use a live `issued_at_ms` within the fixture window (for example `1792180000000`) or a TTL that covers the event timestamps, and assert explicitly that the safe baseline was not used. Document the fixture-timestamp dependency so the test does not silently re-expire.

---

### PLAN-R1-F03 — minor — open — origin: initial

**Location:** `design.md#L246` and `#L251`; `tasks.md#L43`; `backend/core/schemas.py#L18-L32`; `backend/tests/test_architecture.py#L36-L48`.

**Evidence:** The mitigation says "Fixtures keep the optional fields absent" and "Fixtures leave all optional override fields absent". That is true for the four Rust `AssetOverride` literals, but the Python bridge uses `PolicyEnvelope.default_active()`, whose `AssetOverride.to_dict()` emits all eleven keys with Python defaults (`entry_obi_threshold=0.08`, `max_rsi_long=70.0`, `min_rsi_short=30.0`, `take_profit_bps=45.0`, `stop_loss_bps=30.0`, with the three USD zones `None`). The counts still hold because 0.08 is the effective threshold and the router derives PnL from `expected_edge_bps` (`engine-rs/crates/exec-router/src/lib.rs#L56-L57`), but the stated reason is wrong for the Python path and could mislead DEV into changing fixtures.

**Required fix:** Correct the risk text to distinguish the Rust fixtures (`None`) from the Python bridge (explicit defaults); add a comment/assertion in task 6.3 or `test_architecture.py` that the bridge envelope carries those defaults, and keep the "re-baseline only with Rust output evidence" rule.

---

### PLAN-R1-F04 — minor — open — origin: initial

**Location:** `tasks.md#L35` (task 5.2); `backend/core/state_store.py#L573` and `#L642`; `backend/tests/test_metrics_populations.py#L101` and `#L112`.

**Evidence:** Task 5.2 says "both existing call sites", but there are four `compute_paper_execution_pnl` calls: two production sites (`state_store.py#L573`, `#L642`) and two test sites (`test_metrics_populations.py#L101`, `#L112`). The production sites need `rule.min_rsi_short if rule else 30.0`; the test sites use keyword arguments and would silently take the new default 30.0. The production propagation is specified and test 6.6 covers the short side, but the task undercounts and does not pin the parameter placement/default for the two test calls.

**Required fix:** Reword to "both production call sites", specify the parameter position (or that it is keyword-only/defaulted after `pod_id`) so the two test calls remain valid, and note that those test calls intentionally use the 30.0 default.

---

### PLAN-R1-F05 — minor — open — origin: initial

**Location:** `tasks.md#L4` (task 1.2); `design.md#L196-L208`.

**Evidence:** The task explicitly skips `openspec/` and says "never Markdown", which closes the stated self-report risk: `design.md` and `tasks.md` are excluded by path and extension. Residual precision gaps remain. The checker scans `.py` but does not say to strip comments/strings or to exclude itself; a docstring or comment containing `SAFE_BASELINE_TTL_SECONDS=900` in `scripts/check_contract_single_source.py` would be a false duplicate. The "exempt `from_dict`/`default_active`" is inert under the identifier-only predicate (bare `900` never matches), and the negative fixture only adds a `SAFE_BASELINE_TTL_SECONDS=900` line, so the exemption path is never exercised. Task 1.1 also asks for "a comment naming both runtimes"; if that comment repeats the assignment, the checker sees two declarations in the same file.

**Required fix:** Specify comment/string stripping or self-exclusion in task 1.2; state that the contract comment must not contain the assignment; add a test case proving a bare `900` in `from_dict`/`default_active` is not flagged (or define the explicit exemption mechanism the spec mentions).

---

### PLAN-R1-F06 — minor — open — origin: initial

**Location:** `specs/contract/spec.md` — requirement "Hand-maintained contract with executable drift detection", scenario "No codegen is introduced"; `tasks.md` groups 6 and 7.

**Evidence:** No task or Verification step inspects dependency manifests or generated artifacts for codegen. Task 6.4 covers "Drift is caught by the test", but the "No codegen is introduced" scenario has no named verification, while design D1 merely forbids codegen. The checklist requires each scenario to have a task or verification command.

**Required fix:** Add a Verification line or task (for example a `git diff --stat` plus a `grep` for codegen dependencies/build steps/generated contract files) asserting no schema codegen artifact or dependency is introduced.

---

### PLAN-R1-F07 — minor — open — origin: initial

**Location:** `tasks.md#L6` (task 1.4); `tasks.md#L44` (task 6.4); `design.md#L250`.

**Evidence:** Task 1.4 installs the stable Rust toolchain in the Python CI job, which is the necessary install and is explicit. However, the job does not prebuild `robotrader-node`, and the design's "bounded timeout, mirroring the existing bridge test" refers to `run_rust_backtest`'s `timeout=30` (`backend/core/state_store.py#L771-L776`). A cold `cargo run` in the Python job can exceed 30 s; task 6.4 does not pin a timeout or a prebuild. The test can then fail for a build-time reason rather than a contract reason.

**Required fix:** Add a `cargo build --bin robotrader-node` step (optionally with `Swatinem/rust-cache`) to the Python CI job, or specify a timeout that covers a cold build in `test_contract_roundtrip.py`; state the expected binary path.

---

### PLAN-R1-F08 — minor — open — origin: initial

**Location:** `design.md#L103` (D6) and `#L169-L173`; `tasks.md#L25` (task 4.1); `specs/contract/spec.md` — "Momentum pod applies envelope mechanical rules" (`|OBI| >= entry_obi_threshold` for both directions).

**Evidence:** The approved spec states the magnitude condition `|OBI| >= entry_obi_threshold`; the plan adds sign conditions (`long OBI >= t`, `short OBI <= -t`). The design argues this strengthens and does not contradict the spec, and all approved scenarios still hold. It is nevertheless a narrowing not stated literally in the spec; the table-driven suite (task 6.2) is not stated to cover the sign asymmetry.

**Required fix:** Record the interpretation explicitly (the design already does) and add a named test for a long setup with `OBI = -t` (and the short mirror) to pin the sign rule; if the literal magnitude wording is the intended contract, escalate the wording as a spec clarification rather than leaving it implicit.

## Checks run

| Command / inspection | Result |
|---|---|
| `git rev-parse HEAD` | `10721e65e160c4ed8c057a06f81fa89d36e3226d` |
| `openspec validate align-asset-override-contract --strict` | `Change 'align-asset-override-contract' is valid` (exit 0) |
| `scripts/sdlc/sdlc.sh check align-asset-override-contract` | `check: PASS` (exit 0); spec-r1 `CHANGES_REQUESTED`, spec-r2 `APPROVE` |
| Read approved SPEC at `5bc41cd`: `proposal.md`, `specs/contract/spec.md` | read |
| Read `design.md` and `tasks.md` at reviewed SHA | read |
| Read `engine-rs/crates/common/src/lib.rs`, `risk-gate/src/lib.rs`, `strategies/src/lib.rs`, `backtest/src/lib.rs`, `node/src/main.rs` | confirmed line citations above |
| Read `backend/core/schemas.py`, `backend/core/state_store.py`, `backend/tests/test_architecture.py`, `backend/tests/test_metrics_populations.py` | confirmed call sites and bridge assertions |
| Read `Dockerfile.backend`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/ci.yml`, `.gitignore` | confirmed the missing contract copy, CI jobs, and path filters |
| `ls contracts` | directory absent (task 1.1 creates it) |

## Verdict

`CHANGES_REQUESTED` — 2 open blockers, 0 majors, 6 minors. The two blockers are deployment-breaking and verification-breaking, so the plan cannot proceed to DEV. The remaining findings should be folded into the R1 correction so the next round is closure-only.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "10721e65e160c4ed8c057a06f81fa89d36e3226d",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Plan is sound in design but blocked by a missing contracts copy in the Docker build/runtime and by an expired-envelope valid-policy verification that cannot yield total_trades == 0.",
  "findings": [
    {
      "id": "PLAN-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/design.md#L48-L60; Dockerfile.backend#L1-L26; tasks.md#L67",
      "evidence": "The builder copies only engine-rs/Cargo.toml and engine-rs/crates, so include_str!('../../../../contracts/policy_contract.conf') resolves to /build/contracts/policy_contract.conf, which is never copied; the runtime copies only backend, so backend/core/schemas.py resolves /app/contracts/policy_contract.conf, which is absent. The plan's docker compose up --build -d verification cannot pass.",
      "required_fix": "Add a task copying contracts/ into the builder at the include_str! path and into the runtime image at /app/contracts, update the Impact table with Dockerfile.backend, and add a Docker build/import smoke check to Verification."
    },
    {
      "id": "PLAN-R1-F02",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L45; tasks.md#L63",
      "evidence": "The valid-policy fixture uses issued_at_ms: 0 with ttl_seconds: 900, while benchmark events are at 1792180000000; HardRiskGate::validate calls effective(now_ms), is_expired is true, and safe_baseline enables pod_carry and pod_momentum, so total_trades == 0 is false and the test cannot prove the supplied envelope was used.",
      "required_fix": "Use a live issued_at_ms within the fixture window (e.g. 1792180000000) or a covering TTL in both task 6.5 and the Verification command, and assert the safe baseline was not used."
    },
    {
      "id": "PLAN-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/design.md#L246; design.md#L251; tasks.md#L43",
      "evidence": "The mitigation says fixtures leave optional override fields absent; the Rust fixtures do, but the Python bridge uses default_active() whose to_dict() emits all eleven keys with Python defaults (entry_obi_threshold 0.08, max_rsi_long 70.0, min_rsi_short 30.0, take_profit_bps 45.0, stop_loss_bps 30.0).",
      "required_fix": "Correct the risk text to distinguish Rust None fixtures from the Python defaults, and add a comment/assertion in task 6.3 or test_architecture.py confirming the bridge envelope carries those defaults."
    },
    {
      "id": "PLAN-R1-F04",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L35; backend/core/state_store.py#L573; backend/core/state_store.py#L642; backend/tests/test_metrics_populations.py#L101; backend/tests/test_metrics_populations.py#L112",
      "evidence": "Task 5.2 says both existing call sites, but there are four: two production sites and two keyword-argument test sites. Production propagation is specified and test 6.6 covers the short side, but the task undercounts and does not pin parameter placement/default for the test calls.",
      "required_fix": "Reword to 'both production call sites', specify the parameter position or keyword-only default after pod_id, and note that the two test calls intentionally use 30.0."
    },
    {
      "id": "PLAN-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L4; design.md#L196-L208",
      "evidence": "Task 1.2 correctly excludes openspec/ and Markdown, closing the design.md/tasks.md self-report risk. Residual: the checker scans .py without comment/string stripping or self-exclusion; the from_dict/default_active exemption is inert under the identifier-only predicate and is never exercised; the contract comment must not repeat the assignment.",
      "required_fix": "Specify comment/string stripping or self-exclusion, forbid the assignment in the contract comment, and add a case proving bare 900 in from_dict/default_active is not flagged (or define the explicit exemption mechanism)."
    },
    {
      "id": "PLAN-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md (Hand-maintained contract, 'No codegen is introduced'); tasks.md groups 6-7",
      "evidence": "No task or Verification step inspects dependency manifests or generated artifacts for codegen; only the drift test in task 6.4 is planned.",
      "required_fix": "Add a Verification line or task asserting no schema codegen dependency, build step, or generated contract file is introduced."
    },
    {
      "id": "PLAN-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/tasks.md#L6; tasks.md#L44; design.md#L250",
      "evidence": "Task 1.4 installs Rust in the Python CI job, which is necessary. It does not prebuild robotrader-node, and the design's bounded timeout mirrors run_rust_backtest's timeout=30 (state_store.py#L771-L776); a cold cargo build can exceed 30 s and task 6.4 does not pin a timeout or prebuild.",
      "required_fix": "Add a cargo build --bin robotrader-node step to the Python CI job (optionally with rust-cache) or specify a timeout covering a cold build, and state the expected binary path."
    },
    {
      "id": "PLAN-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/design.md#L103; design.md#L169-L173; tasks.md#L25",
      "evidence": "The approved spec states |OBI| >= entry_obi_threshold for both directions; the plan adds long OBI >= t and short OBI <= -t. The design argues this strengthens the spec and all approved scenarios hold, but the sign narrowing is not literal in the spec and the test suite is not stated to cover the sign asymmetry.",
      "required_fix": "Record the interpretation and add a named test for a long setup with OBI = -t and the short mirror; if the magnitude wording is the intended contract, escalate the wording as a spec clarification."
    }
  ],
  "closed": []
}
```
