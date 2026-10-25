stage: spec
round: 1
head_sha: 1fb15ce5721a286c3644bb06b71763545c76ceed
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: "Added the requirement 'CI provisions the Rust binary for the Python suite' (specs/build-packaging/spec.md), requiring the Rust toolchain and `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` before the Python job, with clean-checkout and documented-local-procedure scenarios. Requirement 5 now states the suite depends on the provisioned binary. proposal.md Impact lists README.md, AGENTS.md, .github/workflows/ci.yml, and the affected test modules."
  - id: SPEC-R1-F02
    action: fixed
    evidence: "Requirement 'Actionable missing-binary error on backtest-dependent endpoints' now states a single global exception handler and enumerates all direct endpoints (/status, /hierarchy, /leaf/{leaf_id}/backtest, /backtest/run, /policy/regime, /risk/kill) plus the transitive /api/v1/chat caller in a table. Added scenarios for read endpoints, leaf backtest, backtest/run, policy/regime (preset not applied), risk/kill (kill switch applied), and chat (applied regime remains)."
  - id: SPEC-R1-F03
    action: fixed
    evidence: "Requirement 'One shared Rust binary resolver without a compiler fallback' now specifies debug-first precedence with release fallback. Scenarios 'Debug build is used when present', 'Fresh debug build wins over release', and 'Release is used as the fallback' document the local-development consequence and the container case."
  - id: SPEC-R1-F04
    action: fixed
    evidence: "Requirement 'Helm chart exposes service, ingress, and runtime environment' now specifies `env.redisUrl` default empty (in-memory fallback) and `env.maxDailyLlmBudgetUsd` default 5.0, both documented in values.yaml. Added 'Default environment values are valid' and 'Empty budget override falls back to a valid number' scenarios asserting a positive floating-point budget."
  - id: SPEC-R1-F05
    action: fixed
    evidence: "Split the former combined Ingress scenario into 'Ingress renders when enabled' and 'No Ingress when disabled'."
  - id: SPEC-R1-F06
    action: fixed
    evidence: "Removed the internal-structure THENs. 'Both methods use the selected binary' now asserts the invoked binary path and normal result shape. 'Discovery is stable across supported Python versions' asserts exit 0 and the absence of 'Start directory is not importable'; the causal namespace-package clause was removed."
  - id: SPEC-R1-F07
    action: fixed
    evidence: "Requirement 'CI gates Helm chart changes' now names only the Rust, Python, and frontend jobs in ci.yml, and explicitly states that .github/workflows/sdlc-checks.yml is out of scope and unchanged."
  - id: SPEC-R1-F08
    action: fixed
    evidence: "Removed the container request-path HTTP 200 scenario. Container behavior is covered by 'Release binary is installed' and the debug-first resolver's 'Release is used as the fallback' scenario, avoiding an uncontrolled dependency on hierarchy/RSS/Redis for an HTTP 200 assertion."
  - id: SPEC-R1-F09
    action: fixed
    evidence: "Pruned the duplicate scenarios: removed 'No missing template definition', 'Build uses the committed dependency versions', and 'Container request path uses the release build'. Folded the backend-behaviour assertion into 'No module imports the removed dependency or config'."
  - id: SPEC-R1-F10
    action: fixed
    evidence: "The uniform detail contract is defined once in the requirement (both candidate paths plus the exact `--manifest-path` build command). Every endpoint scenario now references that contract explicitly rather than describing it loosely."
  - id: SPEC-R1-F11
    action: fixed
    evidence: "The required detail command is now `cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node`, which is runnable from the repository root; the requirement states this explicitly."
  - id: SPEC-R1-F12
    action: fixed
    evidence: "Removed the `### Non-goals` subsection from the Review Card in proposal.md; the body `## Non-goals` section is now the single source."
  - id: SPEC-R1-F13
    action: fixed
    evidence: "The resolver requirement now scopes the claim to 'one shared resolver for the backtest methods' and states that the `_rust_binary_candidates` vault-manifest/sign-transfer list in backend/core/hierarchy.py is out of scope and must remain unchanged. proposal.md adds a matching Non-goal."
