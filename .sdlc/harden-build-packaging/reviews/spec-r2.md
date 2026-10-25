# SPEC Review — Round 2

## Summary

R2 closes all 13 R1 findings at `2a7f035`; the verdict is APPROVE with zero open blocker/major. The blocker and three majors are resolved: CI now provisions the Rust binary before the Python suite with a root-runnable `--manifest-path` build, Impact lists the three affected test modules plus `README.md`/`AGENTS.md`/`ci.yml`, and no requirement relies on the removed `cargo run` fallback. The 503 contract enumerates all six direct HTTP callers plus the transitive `/chat` with a side-effect table; the resolver is debug-first with release fallback and a scenario proving the container resolves release; `values.yaml` defaults are specified with default-render and empty-override scenarios. The nine minors/nits are fixed. All mandated checks pass. Non-blocking follow-ups: `/ws/chat` shares `process_user_command` but cannot return a 503 JSON; the "Default environment values are valid" scenario embeds a non-render assertion about `values.yaml`; the `/policy/regime` no-side-effect THEN requires DEV to commit the preset only after a successful backtest.

## Findings

### SPEC-R1-F01 — [blocker] Documented test command contradicts the no-compiler resolver and CI provides no binary
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L89` and `#L109-L124`; `proposal.md#L87-L88`
- Evidence: The new requirement "CI provisions the Rust binary for the Python suite" mandates the Rust toolchain and a root-runnable `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` before discovery, with clean-checkout and documented-local-procedure scenarios. The package-marker requirement now conditions discovery on the provisioned binary. Impact lists `backend/tests/test_architecture.py`, `test_hierarchy_v3.py`, `test_metrics_populations.py`, `README.md`, `AGENTS.md`, and `.github/workflows/ci.yml`. Grep confirms those are the only resolver-touching test modules and the only `cargo run` mention in the delta is the negative "No compiler is invoked" assertion.
- Required fix: (original) Specify binary provisioning for the test path and list the affected tests/CI files in Impact.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] "Every endpoint" 503 contract is not enumerated or tested
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L159-L216`; `proposal.md#L89`
- Evidence: The requirement now mandates one global exception handler and carries a table enumerating `GET /api/v1/status`, `GET /api/v1/hierarchy`, `POST /api/v1/backtest/run`, `POST /api/v1/leaf/{leaf_id}/backtest`, `POST /api/v1/policy/regime`, `POST /api/v1/risk/kill`, and the transitive `POST /api/v1/chat`, each with its side effect; dedicated scenarios cover each group. Independent grep of `backend/server.py` finds exactly those six direct call sites (L101, L144, L235, L314, L325, L336); the only other runtime path is `orchestrator.process_user_command` (L1022/1037/1051), which is `/chat`.
- Required fix: (original) Enumerate every affected endpoint, state the handler strategy, and specify state side effects.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] Release-first silently shadows a fresh local debug build
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L126-L157`; `proposal.md#L7,L26,L57`
- Evidence: The resolver requirement now mandates debug-first precedence with `engine-rs/target/release/robotrader-node` as the fallback, plus "Debug build is used when present", "Fresh debug build wins over release", and "Release is used as the fallback" scenarios; the last scenario explicitly states the container has no debug binary and resolves release.
- Required fix: (original) Invert to debug-first/release-fallback and document the local consequence.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] New Helm env values have no specified valid defaults
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L21-L59`; `proposal.md#L89`
- Evidence: The requirement now mandates `env.redisUrl` default `""` (in-memory fallback) and `env.maxDailyLlmBudgetUsd` default `5.0`, both documented in `values.yaml`, and a non-empty numeric budget even on an empty override. Scenarios "Default environment values are valid" and "Empty budget override falls back to a valid number" assert a positive float (and exact `5.0` on empty). Code check: `backend/core/state_store.py:162` treats an empty `REDIS_URL` as in-memory, and `backend/agents/monitor.py:78` would raise on an empty budget, confirming the requirement is necessary and the fallback is the right one.
- Required fix: (original) Specify defaults, document the keys, and add default-render/empty-override scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [minor] Ingress scenario mixes enabled and disabled behavior
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L31-L39`
- Evidence: Split into "Ingress renders when enabled" and "No Ingress when disabled", one WHEN/THEN behavior each.
- Required fix: (original) Split the scenario.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [minor] Internal assertions used as observable THENs
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L130-L134,L103-L107`
- Evidence: The structural clauses ("neither method constructs its own binary path", "the markers make the directory importable") are removed. "Both methods use the selected binary" now asserts the invoked path and the normal result shape; "Discovery is stable across supported Python versions" asserts exit 0 and the absence of the importability error.
- Required fix: (original) Rephrase as observable behavior.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [minor] CI requirement names the SDLC job, but no scenario covers it
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L218-L244`
- Evidence: The requirement now names only the Rust, Python, and frontend jobs in `ci.yml` and explicitly states `.github/workflows/sdlc-checks.yml` is out of scope and unchanged; the retention scenario covers only those three jobs, matching the requirement.
- Required fix: (original) Drop SDLC or add a scenario.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [minor] Container request-path scenario is not guaranteed by its precondition
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L77-L85,L147-L151`
- Evidence: The uncontrolled HTTP 200 scenario is removed. Container behavior is now covered by "Release binary is installed" (path exists, debug absent) and the resolver's "Release is used as the fallback" scenario, with no dependency on hierarchy/RSS/Redis.
- Required fix: (original) Assert the selected binary or use a controlled integration test.
- Status: closed
- Origin: initial

### SPEC-R1-F09 — [nit] Duplicated scenarios add verification cost without distinct behavior
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md`
- Evidence: "No missing template definition", "Build uses the committed dependency versions", and "Container request path uses the release build" are removed; the backend-behavior assertion is folded into "No module imports the removed dependency or config". Remaining scenarios guard distinct failure modes.
- Required fix: (original) Merge or prune duplicates.
- Status: closed
- Origin: initial

### SPEC-R1-F10 — [minor] The 503 detail contract is only fully asserted for `/status`
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L161,L175-L210`
- Evidence: The uniform contract (both candidate paths plus the exact build command) is defined once in the requirement, and every endpoint scenario now references "the uniform detail contract defined in this requirement" instead of paraphrasing it.
- Required fix: (original) State the exact detail content once and reference it everywhere.
- Status: closed
- Origin: initial

### SPEC-R1-F11 — [minor] The required build command is not runnable from the repository root
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L111,L117,L161`
- Evidence: Both the CI requirement and the 503 detail now use `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node` (the CI scenario omits `--release`, which matches the debug-first suite). The `--manifest-path` form resolves `engine-rs/Cargo.toml`, so it runs from the repository root.
- Required fix: (original) Use a root-runnable command form.
- Status: closed
- Origin: initial

### SPEC-R1-F12 — [nit] Duplicate Non-goals section
- Location: `openspec/changes/harden-build-packaging/proposal.md#L73-L83`
- Evidence: The Review Card no longer has a `### Non-goals` subsection; `## Non-goals` appears exactly once in the proposal (grep).
- Required fix: (original) Keep a single Non-goals section.
- Status: closed
- Origin: initial

### SPEC-R1-F13 — [minor] "One resolver" scope is ambiguous versus the existing hierarchy resolver
- Location: `openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L128`; `proposal.md#L67,L78`
- Evidence: The requirement scopes the claim to "one shared resolver for the backtest methods" and states the `backend/core/hierarchy.py` vault-manifest/sign-transfer candidate list is out of scope and MUST remain unchanged; the proposal adds a matching Non-goal and scopes the capability text to the two backtest methods.
- Required fix: (original) State the hierarchy resolver is out of scope or route it through the shared resolver.
- Status: closed
- Origin: initial

## Checks run

- `openspec validate harden-build-packaging --strict` → PASS ("Change 'harden-build-packaging' is valid", exit 0).
- `scripts/sdlc/spec-lint.py --change harden-build-packaging` → PASS; Review Card 172 words, 1 diagram, ~1.4 min.
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → PASS (OpenSpec, spec-lint, verdict-lint).
- Independent code verification: resolver call sites in `backend/server.py`, transitive `/chat` via `backend/agents/orchestrator.py`, `REDIS_URL` fallback in `backend/core/state_store.py:162`, budget parsing in `backend/agents/monitor.py:78`, affected test modules, and the documented commands in `README.md:201` / `AGENTS.md:90`.
- Read time: 1.4 min (Review Card; spec-lint estimate).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "2a7f0350c6915cbbff25dc2ec1620d5993ec2170",
  "verdict": "APPROVE",
  "summary": "All 13 R1 findings are closed at 2a7f035; the CI binary provisioning, endpoint enumeration, debug-first resolver, and Helm env defaults are specified and testable, with no open blocker or major.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L89,L109-L124; proposal.md#L87-L88",
      "evidence": "CI-provisioning requirement mandates the Rust toolchain and a root-runnable --manifest-path build before discovery, with clean-checkout and local-procedure scenarios; Impact lists the three affected test modules plus README.md, AGENTS.md, and ci.yml; no requirement relies on cargo run.",
      "required_fix": "Specify binary provisioning for the test path and list the affected tests/CI files in Impact."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L159-L216; proposal.md#L89",
      "evidence": "One global handler plus a table enumerating all six direct callers (/status, /hierarchy, /backtest/run, leaf backtest, /policy/regime, /risk/kill) and the transitive /chat, each with side effects; scenarios cover every group. Independent grep confirms no other HTTP caller.",
      "required_fix": "Enumerate every affected endpoint, state the handler strategy, and specify state side effects."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L126-L157",
      "evidence": "Debug-first with release fallback; scenarios cover debug-only, both-present, release-fallback, and the container resolving release because debug is absent.",
      "required_fix": "Invert to debug-first/release-fallback and document the local consequence."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L21-L59; proposal.md#L89",
      "evidence": "env.redisUrl defaults to empty (verified in-memory fallback at state_store.py:162) and env.maxDailyLlmBudgetUsd to 5.0; default-render and empty-override scenarios assert a positive float, matching monitor.py:78's float parse.",
      "required_fix": "Specify defaults, document the keys, and add default-render/empty-override scenarios."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L31-L39",
      "evidence": "Split into 'Ingress renders when enabled' and 'No Ingress when disabled'.",
      "required_fix": "Split the scenario."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L130-L134,L103-L107",
      "evidence": "Structural clauses removed; THENs now assert the invoked binary path, the normal result shape, exit 0, and the absence of the importability error.",
      "required_fix": "Rephrase as observable behavior."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L218-L244",
      "evidence": "Requirement names only the Rust/Python/frontend jobs and states sdlc-checks.yml is out of scope and unchanged; the retention scenario matches.",
      "required_fix": "Drop SDLC or add a scenario."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L77-L85,L147-L151",
      "evidence": "Uncontrolled HTTP 200 scenario removed; container coverage is limited to the release-binary install and resolver fallback scenarios.",
      "required_fix": "Assert the selected binary or use a controlled integration test."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md",
      "evidence": "The three named duplicate scenarios are removed and the folded assertion retained once.",
      "required_fix": "Merge or prune duplicates."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L161,L175-L210",
      "evidence": "The uniform detail contract is defined once and every endpoint scenario references it explicitly.",
      "required_fix": "State the exact detail content once and reference it everywhere."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L111,L117,L161",
      "evidence": "The command now uses --manifest-path engine-rs/Cargo.toml, which is runnable from the repository root.",
      "required_fix": "Use a root-runnable command form."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/proposal.md#L73-L83",
      "evidence": "Only one Non-goals section remains; the Review Card subsection is gone.",
      "required_fix": "Keep a single Non-goals section."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/harden-build-packaging/specs/build-packaging/spec.md#L128; proposal.md#L67,L78",
      "evidence": "The requirement scopes the shared resolver to the two backtest methods and declares the hierarchy.py candidate list out of scope and unchanged; the proposal carries the matching Non-goal.",
      "required_fix": "State the hierarchy resolver is out of scope or route it through the shared resolver."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08",
    "SPEC-R1-F09",
    "SPEC-R1-F10",
    "SPEC-R1-F11",
    "SPEC-R1-F12",
    "SPEC-R1-F13"
  ]
}
```
