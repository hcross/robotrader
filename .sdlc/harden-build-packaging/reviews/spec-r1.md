# SPEC Review — Round 1

## Summary

R1 returns CHANGES_REQUESTED with one blocker and three majors. The blocker is a direct contradiction between the documented Python test command and the no-compiler resolver: the suite's Rust-backtest tests and the CI Python job still rely on the `cargo run` fallback, and the spec neither builds nor stubs a binary, so the documented command cannot pass in a clean checkout. The majors are: the 503 contract says "every endpoint" but only `/status` and the leaf backtest are specified (hierarchy, backtest/run, policy/regime, risk/kill, chat are omitted); release-first silently shadows a fresh local debug build and contradicts the issue's stated concern; and the new Helm env keys have no specified valid defaults, so an empty `MAX_DAILY_LLM_BUDGET_USD` crashes CostGuard at startup. Minors cover scenario independence, internal THENs, CI/SDLC scope, the exact detail command, and resolver scope. The spec is otherwise well-structured and all mandated checks pass.

## Findings

### SPEC-R1-F01 — [blocker] Documented test command contradicts the no-compiler resolver and CI provides no binary
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L87-L107` and `#L109-L133`
- Evidence: `backend/tests/test_architecture.py:53`, `backend/tests/test_hierarchy_v3.py:48,103,108`, and `backend/tests/test_metrics_populations.py:63` call `run_rust_backtest`/`run_rust_backtest_for_leaf`. `backend/core/state_store.py:752-764` currently falls back to `cargo run` when no binary exists; Req 6 removes that fallback. `.github/workflows/ci.yml:36-51` runs the Python suite with only Poetry/backend dependencies and never builds `robotrader-node`. `engine-rs/target/` is gitignored (`.gitignore:5`), so a clean CI checkout has no binary. `test_metrics_populations.py` patches `subprocess.run`, but the resolver checks `Path.exists()` first, so the patch does not help. Therefore Req 5's "MUST exit 0" cannot hold in CI or a clean checkout after Req 6; `proposal.md#L89` (Impact) omits `backend/tests/**` and any Rust build step in the Python job.
- Required fix: Specify how the suite obtains a binary: add `cargo build --release --bin robotrader-node` (with the Rust toolchain) to the Python CI job and document the local prerequisite, or update the affected tests to stub/patch the resolver or use a fixture binary. Add a scenario that runs the documented command in a clean checkout with no prebuilt binary and add the affected test/CI files to Impact.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] "Every endpoint" 503 contract is not enumerated or tested
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L135-L162`; `proposal.md#L8`
- Evidence: Direct callers in `backend/server.py` are `/api/v1/status` (L101), `/api/v1/hierarchy` (L144), `/api/v1/leaf/{leaf_id}/backtest` (L235), `/api/v1/backtest/run` (L314), `/api/v1/policy/regime` (L325), and `/api/v1/risk/kill` (L336). `/api/v1/chat` invokes the resolver transitively via `orchestrator.process_user_command` (`backend/agents/orchestrator.py:1022,1037,1051`). Only `/status` and the leaf backtest have scenarios; `/hierarchy` is named in the proposal's Risk (`proposal.md#L8`) but has no scenario. The requirement says "every ... endpoint", so an implementation could satisfy the two scenarios and leave the others returning 500.
- Required fix: Enumerate every affected endpoint (direct and transitive) in the requirement and add a scenario or a table-driven test for each, or narrow the requirement to the two endpoints and state the others are unchanged. State whether the mapping is a global exception handler or per-endpoint, and specify the expected state side effects for `/policy/regime` and `/risk/kill`, which mutate before calling the backtest.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] Release-first silently shadows a fresh local debug build
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L109-L122`
- Evidence: `run_rust_backtest` currently uses only `target/debug` (`backend/core/state_store.py:748`); `run_rust_backtest_for_leaf` uses debug then release (`backend/core/state_store.py:791-792`). Issue #9.3 states the current workaround "will silently shadow a locally built debug binary"; the issue's suggested direction #3 is to copy the release binary to `target/release` "and let the lookup order do its job" (debug-first). The spec flips precedence to release-first; when both binaries exist, a stale release build shadows a fresh debug build for both methods. The container only contains release, so debug-first is sufficient there.
- Required fix: Invert to debug-first/release-fallback and update the scenario, or keep release-first only behind an explicit opt-in/env var with a recorded rationale (PLAN) and a scenario documenting the stale-release behavior. Document the local-development consequence.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] New Helm env values have no specified valid defaults
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L25-L47`; `backend/agents/monitor.py:77-79`
- Evidence: The requirement says the Deployment must expose `REDIS_URL` and `MAX_DAILY_LLM_BUDGET_USD` "with values driven by chart values"; the only scenario uses `--set` explicit values and does not test the default render. `MAX_DAILY_LLM_BUDGET_USD` is parsed by `float(os.getenv("MAX_DAILY_LLM_BUDGET_USD", "5.0"))`; an empty string (a plausible `values.yaml` default, matching `env.openrouterApiKey: ""`) raises `ValueError` in `LLMMonitorAgent.__init__` and prevents startup. `charts/robotrader/values.yaml` currently has no `env.redisUrl`/`env.maxDailyLlmBudgetUsd` keys or documentation.
- Required fix: Specify defaults (`env.redisUrl` empty or a valid URL; `env.maxDailyLlmBudgetUsd: 5.0`), document the keys in `values.yaml`, and add a scenario asserting the default render produces a numeric budget and a valid/empty Redis URL, and that the backend does not parse an empty budget.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [minor] Ingress scenario mixes enabled and disabled behavior
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L35-L40`
- Evidence: One `#### Scenario: Ingress renders only when enabled` contains two WHEN/THEN pairs: `ingress.enabled=true` renders an Ingress, and `ingress.enabled=false` renders none. Checklist §5 requires one behavior per scenario.
- Required fix: Split into `Ingress renders when enabled` and `No Ingress when disabled`.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [minor] Internal assertions used as observable THENs
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L113-L117` and `#L103-L107`
- Evidence: "neither method constructs its own binary path" and "the package markers, not namespace-package behaviour, make the start directory importable" assert code structure/causality, not an observable outcome; checklist §5 says the THEN is an observable outcome, not an internal call.
- Required fix: Rephrase as observable behavior (both methods return the same result for a given binary layout; the command passes with the markers present), or move the structural assertion to the PLAN design.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [minor] CI requirement names the SDLC job, but no scenario covers it
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L164-L190`
- Evidence: `.github/workflows/ci.yml` contains only rust/python/frontend; the SDLC job is in `.github/workflows/sdlc-checks.yml`. The scenario "Existing CI jobs and triggers are retained" covers only Rust/Python/frontend, while the requirement says "Rust, Python, frontend, and SDLC jobs MUST remain."
- Required fix: Drop "SDLC" from this requirement or add a scenario asserting `sdlc-checks.yml` is unchanged and still covers `openspec/**`, `sdlc/**`, `docs/sdlc/**`, `scripts/sdlc/**`, `.claude/**`, `.agent/**`, and `.github/**`.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [minor] Container request-path scenario is not guaranteed by its precondition
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L81-L85`
- Evidence: `/api/v1/status` also calls `get_population_metrics`, `get_hierarchy_snapshot` (26 leaves, RSS, MemPalace), and `orchestrator.get_cognitive_state`; the scenario only requires the Rust binary and asserts HTTP 200, so missing network/Redis/services can still fail the request. It also duplicates the resolver scenario.
- Required fix: Assert the selected/executed binary (for example via a stubbed subprocess or log) rather than the whole HTTP 200, or state the full precondition and move the check to a controlled integration test.
- Status: open
- Origin: initial

### SPEC-R1-F09 — [nit] Duplicated scenarios add verification cost without distinct behavior
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L19-L23` vs `#L7-L11`; `#L65-L69` vs `#L59-L63`; `#L81-L85` vs `#L113-L122`
- Evidence: "No missing template definition" re-renders the default chart already covered by "Default render succeeds"; "Build uses the committed dependency versions" overlaps "Inconsistent lockfile fails"; "Container request path uses the release build" overlaps the resolver precedence scenarios.
- Required fix: Merge or prune duplicates, keeping only the distinct failure mode each one guards.
- Status: open
- Origin: initial

### SPEC-R1-F10 — [minor] The 503 detail contract is only fully asserted for `/status`
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L139-L150`
- Evidence: The status scenario asserts the exact substrings; the leaf scenario says "follows the same path-and-build-command contract" without repeating them. Once the other endpoints are added (F02), the contract must be uniform and testable.
- Required fix: State the exact required detail content once (release path plus runnable build command) and reference it from every endpoint scenario, or repeat the assertions per endpoint.
- Status: open
- Origin: initial

### SPEC-R1-F11 — [minor] The required build command is not runnable from the repository root
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L139-L144`
- Evidence: The required detail substring is `cargo build --release --bin robotrader-node`; the Cargo workspace is `engine-rs/Cargo.toml`, so from the repository root the command fails with "could not find Cargo.toml". Issue #9.5 asks for an actionable error.
- Required fix: Require `cd engine-rs && cargo build --release --bin robotrader-node` or `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node` in the detail, and update the scenario substring.
- Status: open
- Origin: initial

### SPEC-R1-F12 — [nit] Duplicate Non-goals section
- Location: `openspec/changes/harden-build-packaging/proposal.md#L38-L41` and `#L77-L85`
- Evidence: `### Non-goals` under the Review Card and `## Non-goals` in the body repeat the same exclusions (#9.6, Redis dependency, strands removal). The config rules require the `## Non-goals` section; the Review Card duplicate is redundant.
- Required fix: Remove the Review Card subsection or fold its content into the main section.
- Status: open
- Origin: initial

### SPEC-R1-F13 — [minor] "One resolver" scope is ambiguous versus the existing hierarchy resolver
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L109-L111`; `proposal.md#L71`
- Evidence: The proposal's capability text says "one Rust binary resolver with no compiler fallback", but `backend/core/hierarchy.py:991-996` already has a separate `_rust_binary_candidates` (release-first) used for `--vault-manifest` and `--sign-transfer`. The delta scopes only `run_rust_backtest` and `run_rust_backtest_for_leaf`, so two resolvers remain.
- Required fix: State explicitly that the hierarchy resolver is out of scope and why, or route `hierarchy.py` through the shared resolver (with its different command arguments) so the "one resolver" claim is true.
- Status: open
- Origin: initial

## Checks run

- `openspec validate harden-build-packaging --strict` → PASS ("Change 'harden-build-packaging' is valid", exit 0).
- `scripts/sdlc/spec-lint.py --change harden-build-packaging` → PASS; Review Card 183 words, 1 diagram, ~1.4 min; warnings only for `design.md`/`tasks.md` not present yet (PLAN stage).
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → PASS (OpenSpec, spec-lint, and verdict-lint checks); "no verdicts found" expected before this R1 file.
- `helm template charts/robotrader` → exit 1 with `no template "robotrader.fullname"`, confirming the issue's current failure.
- `helm lint charts/robotrader` → exit 1, same error, confirming the issue's current failure.
- Read time: 1.4 min (spec-lint estimate; Review Card within the 5-minute budget).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "1fb15ce5721a286c3644bb06b71763545c76ceed",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The no-compiler resolver breaks the documented Python test command and CI, the 503 contract is specified for only two of six endpoints, release-first silently shadows local debug builds, and the Helm env defaults are unspecified.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L87-L107 and #L109-L133",
      "evidence": "Tests at backend/tests/test_architecture.py:53, test_hierarchy_v3.py:48,103,108, and test_metrics_populations.py:63 call the resolver; state_store.py:752-764 currently falls back to cargo run; .github/workflows/ci.yml:36-51 never builds robotrader-node; engine-rs/target is gitignored. Req 5 cannot pass in CI/clean checkout after Req 6, and Impact omits tests and the CI Rust build step.",
      "required_fix": "Specify binary provisioning for the test path: add a Rust build step to the Python CI job and document the local prerequisite, or update the affected tests to stub/patch the resolver or use a fixture binary; add a clean-checkout scenario and the affected test/CI files to Impact."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L135-L162; proposal.md#L8",
      "evidence": "Direct resolver callers are server.py:101 (/status), :144 (/hierarchy), :235 (/leaf/{leaf_id}/backtest), :314 (/backtest/run), :325 (/policy/regime), :336 (/risk/kill); /chat is transitive via orchestrator.py:1022,1037,1051. Only /status and the leaf backtest have scenarios; /hierarchy is named in the proposal Risk but untested.",
      "required_fix": "Enumerate every affected endpoint (direct and transitive) and add a scenario or table-driven test for each, or narrow the requirement explicitly. State whether the mapping is global or per-endpoint and specify state side effects for policy/regime and risk/kill."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L109-L122",
      "evidence": "run_rust_backtest uses only target/debug (state_store.py:748); run_rust_backtest_for_leaf uses debug then release (state_store.py:791-792). Issue #9.3 warns the workaround shadows a local debug binary; suggested direction #3 keeps the lookup order (debug-first). The spec flips to release-first, so a stale release shadows a fresh debug build when both exist.",
      "required_fix": "Invert to debug-first/release-fallback and update the scenario, or keep release-first only behind an explicit opt-in/env var with a PLAN rationale and a stale-release scenario; document the local-development consequence."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L25-L47; backend/agents/monitor.py:77-79",
      "evidence": "The env scenario only tests explicit --set values and never the default render. MAX_DAILY_LLM_BUDGET_USD is parsed by float(os.getenv(...,\"5.0\")); an empty string raises ValueError in LLMMonitorAgent.__init__ and prevents startup. values.yaml has no env.redisUrl/env.maxDailyLlmBudgetUsd keys or documentation.",
      "required_fix": "Specify defaults (env.redisUrl empty or a valid URL; env.maxDailyLlmBudgetUsd: 5.0), document the keys in values.yaml, and add a default-render scenario asserting a numeric budget and a valid/empty Redis URL and that an empty budget is not parsed."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L35-L40",
      "evidence": "The Ingress scenario contains two WHEN/THEN pairs (enabled renders; disabled renders nothing), violating checklist section 5's one-behavior-per-scenario rule.",
      "required_fix": "Split into Ingress renders when enabled and No Ingress when disabled."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L113-L117 and #L103-L107",
      "evidence": "THEN clauses assert internal structure/causality: neither method constructs its own binary path, and the markers (not namespace packages) make the directory importable. Checklist section 5 requires an observable outcome.",
      "required_fix": "Rephrase as observable behavior or move the structural assertions to the PLAN design."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L164-L190",
      "evidence": "ci.yml has only rust/python/frontend; the SDLC job lives in sdlc-checks.yml, and the retention scenario omits SDLC while the requirement names it.",
      "required_fix": "Drop SDLC from this requirement or add a scenario asserting sdlc-checks.yml is unchanged and still covers its path filters."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L81-L85",
      "evidence": "/status also calls get_population_metrics, get_hierarchy_snapshot, and orchestrator.get_cognitive_state; requiring only the Rust binary is insufficient for the asserted HTTP 200, and the scenario duplicates the resolver precedence check.",
      "required_fix": "Assert the selected/executed binary rather than the whole response, or state the full precondition and use a controlled integration test."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L19-L23 vs #L7-L11; #L65-L69 vs #L59-L63; #L81-L85 vs #L113-L122",
      "evidence": "Several scenarios restate behavior already covered by default render, lockfile failure, or resolver precedence scenarios, adding verification cost without a distinct failure mode.",
      "required_fix": "Merge or prune duplicates, keeping only distinct regression guards."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L139-L150",
      "evidence": "Only the status scenario asserts the exact detail substrings; the leaf scenario refers to the same contract by description, making uniform verification ambiguous.",
      "required_fix": "State the exact detail content once and reference it from every endpoint scenario, or repeat the assertions per endpoint."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L139-L144",
      "evidence": "The required detail substring cargo build --release --bin robotrader-node is not runnable from the repository root because the workspace is engine-rs/Cargo.toml; the error is not fully actionable.",
      "required_fix": "Require cd engine-rs && cargo build --release --bin robotrader-node or the --manifest-path form, and update the scenario."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/proposal.md#L38-L41 and #L77-L85",
      "evidence": "Non-goals appears twice: a Review Card subsection and the required body section, repeating the same exclusions.",
      "required_fix": "Remove the Review Card subsection or fold it into the main Non-goals section."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L109-L111; proposal.md#L71",
      "evidence": "The proposal claims one Rust binary resolver, but hierarchy.py:991-996 has a separate release-first _rust_binary_candidates for vault-manifest and sign-transfer; the delta scopes only the two backtest methods.",
      "required_fix": "State that the hierarchy resolver is out of scope and why, or route it through the shared resolver so the one-resolver claim holds."
    }
  ],
  "closed": []
}
```
