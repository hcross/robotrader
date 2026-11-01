# PLAN Review — Round 1

## Summary
Approved (Round 1). The design (`design.md`) and tasks (`tasks.md`) at commit `f7523c317c5ae136da94422a1fe782af7d7a22ef` thoroughly and accurately trace all requirements and invariants from the approved specifications (`bip32-cryptographic-vault` and `vault-simulation`). All 13 technical decisions (D1–D13) have explicit alternatives, sound technical rejection rationales, and clear reversibility. Runtime selection via `ROBOTRADER_VAULT_MODE` preserves complete backward compatibility and simulation test invariants by default. The plan respects hot-path latency budgets (vault operations occur solely on the warm path), enforces zero Python key custody, eliminates prefix wildcard bypasses with strict allowlisting and address checksum validation, and guarantees RAM zeroization of ephemeral keys. The task breakdown is sequentially ordered by dependency, testable in single sessions, and includes comprehensive verification commands. Zero open blockers or majors.

## Findings

No open blocker, major, minor, or nit findings.

## Checklist Walk

### 1. Traceability
- [x] Every design decision traces to a requirement or an invariant: **PASS**. Decisions D1–D13 map directly to delta spec requirements (D1: vault mode selection; D2: pure-Rust crypto dependencies; D3–D4: BIP-32/SLIP-0010/Substrate derivation; D5–D6: address formatting and `validate_chain_address`; D7: strict allowlisting; D8–D10: digital checkout signing and ephemeral zeroization; D11: master seed precedence; D12: receipt schema parity; D13: CLI dispatch).
- [x] Every requirement is addressed by at least one task: **PASS**. All 6 requirements from `bip32-cryptographic-vault` and all 8 requirements from `vault-simulation` are addressed across tasks 1.1–8.3, with explicit scenario mappings on each task.
- [x] No task implements behavior that is not in the spec: **PASS**. Tasks are strictly confined to approved capabilities, contract synchronization, address derivation, and validation.
- [x] A spec gap is escalated as `spec-gap`, not patched in `design.md`: **PASS**. No spec gaps discovered; design strictly honors approved delta specs.

### 2. Decisions
- [x] Each decision names the alternatives considered: **PASS**. Table in `design.md` lines 125–140 lists concrete alternatives for all 13 decisions.
- [x] Each rejection has a technical reason, not a preference: **PASS**. Every rejection cites architectural and cryptographic justifications (e.g. dynamic dispatch overhead, C FFI cross-compilation risks, non-BIP32 mathematical incompatibility, regex catastrophic backtracking).
- [x] Reversible decisions are separated from one-way doors: **PASS**. Dual-mode runtime selection via `ROBOTRADER_VAULT_MODE` provides an immediate, zero-state-loss runtime rollback path.
- [x] The simplest design that satisfies the spec was considered first: **PASS**. Pure-Rust crates from standard ecosystems and stateless CLI/risk-gate execution chosen without complex IPC or daemon architectures.
- [x] New dependencies are justified: maintenance, license, security, size: **PASS**. Decision D2 justifies `k256`, `ed25519-dalek`, `sha2`, `hmac`, `ripemd`, `sha3`, `blake2`, `bs58`, and `bech32` for audit pedigree and zero external C FFI.

### 3. Contracts and data
- [x] `PolicyEnvelope` parity between Rust and Python is addressed when touched: **PASS**. `PolicyEnvelope` is untouched; `SignedTransferReceipt` schema synchronization across `common/src/lib.rs` and `schemas.py` is explicitly planned in tasks 1.2 and 7.2.
- [x] IPC/API/DB/CLI changes are versioned or backward compatible: **PASS**. `ROBOTRADER_VAULT_MODE` defaults to `SIMULATED`; receipt and manifest models preserve optional/additive fields.
- [x] Schema evolution has a migration and a rollback: **PASS**. Detailed 7-step deployment order and 4-step rollback procedure documented in `design.md` lines 152–167.
- [x] Serialization boundaries are explicit (JSON, MessagePack, Redis TTL): **PASS**. Serde JSON for CLI and Pydantic models for FastAPI explicitly specified.
- [x] No implicit cross-chain or cross-venue data leakage: **PASS**. Per-leaf derivation paths and addresses remain strictly isolated across the 26 leaves.

### 4. Hot path and performance
- [x] No LLM, blocking I/O, unbounded sleep, allocation, or logging in the hot path: **PASS**. Vault key derivation and signing execute solely on the warm path (manifest queries and treasury checkout); hot-path `HardRiskGate::validate` and strategy pods are unaffected (`design.md` line 148).
- [x] The 50µs `HardRiskGate` budget is preserved; a measurement plan exists if touched: **PASS**. Criterion benchmark verification command included in `tasks.md` line 59.
- [x] New loops or data structures have a complexity bound: **PASS**. Address validation and allowlisting operate in linear time over fixed-size buffers with bounded string lengths.
- [x] Backpressure and failure modes are defined (Redis down, RPC down, exchange down): **PASS**. Missing Rust binary, parse errors, or non-zero exit codes cleanly yield HTTP 503 without mutating state (`design.md` lines 75–83, 90–92).

### 5. Safety and security
- [x] Capital protection is not weakened (dry powder, Kelly, drawdown, CostGuard): **PASS**. Treasury checkout rejection fails closed before mutating `total_capital_usd`, leaf allocations, or checkout history.
- [x] Vault/key material stays inside the enclave; zeroization and whitelist are preserved: **PASS**. Private keys wrapped in `ZeroizingBytes<32>` with RAM volatile wiping; Python retains zero key custody.
- [x] Inputs crossing trust boundaries are validated: **PASS**. Two-tier gate enforces `validate_chain_address` and exact allowlist matching before any key is derived or loaded.
- [x] Secrets never enter logs, fixtures, transcripts, or evidence: **PASS**. Explicitly documented in `design.md` line 143; test seeds restricted to non-live opt-in.
- [x] Failure is fail-closed on money/risk paths: **PASS**. Unrecognized vault mode, invalid seed entropy, unlisted destination, invalid checksum, or active kill-switch all fail closed.

### 6. Test strategy
- [x] Each scenario has a named test or verification command: **PASS**. All 22 spec scenarios are mapped to named implementation tasks and verification commands in `tasks.md`.
- [x] Unit, integration, and end-to-end coverage are proportioned to the risk: **PASS**. Comprehensive test suite planned spanning vector tests (EIP-55, Bech32, Base58Check), allowlist enforcement, CLI invocation, and Python hierarchy checkout.
- [x] Determinism: backtest == paper == live is preserved or explicitly addressed: **PASS**. Simulated vault preserved by default for determinism; cryptographic mode uses deterministic HD derivation.
- [x] Negative and boundary tests are planned: **PASS**. Syntactically invalid addresses, checksum mismatches, unlisted destinations, tampered signatures, kill switch triggers, and missing seeds are tested.
- [x] Performance tests are planned where a budget exists: **PASS**. `cargo bench` benchmark step included in `tasks.md` line 59.
- [x] Test data contains no real keys or production data: **PASS**. Uses standard public test vectors and deterministic devnet seed.

### 7. Rollout and rollback
- [x] Deployment order is explicit (migration, service, feature flag): **PASS**. 7-stage phased deployment order specified in `design.md` lines 152–160.
- [x] Rollback is a concrete procedure, not "revert the PR": **PASS**. Step-by-step procedure documented in `design.md` lines 161–167 (env var toggle, container restart, git revert, zero state loss).
- [x] Observability is planned: metrics, logs, alerts, dashboard impact: **PASS**. Manifest metadata, receipt audit fields, and UI badge updates (`CRYPTO_HD_BIP32` / `SIMULATED`) planned in task 8.2.
- [x] Cost impact is assessed (LLM spend, infra, RPC): **PASS**. Pure Rust compute; zero LLM spend or external RPC load incurred.

### 8. Tasks
- [x] Tasks are checkboxes `- [ ] X.Y` grouped under numbered headings: **PASS**. 22 checkbox tasks organized under 8 numbered headings.
- [x] Each task fits one session and is verifiable: **PASS**. Tasks are modularly scoped to individual subsystems and contracts.
- [x] Dependency order is correct; no circular task dependency: **PASS**. Dependency sequence: dependencies/schemas -> derivation -> address encoding -> validation -> signing -> backend selection -> Python integration -> docs/UI.
- [x] `## Verification` lists exact commands and expected evidence: **PASS**. `tasks.md` lines 56–65 details exact CLI, test, benchmark, and lint commands with expected outputs.
- [x] No task hides a spec change: **PASS**. All tasks strictly implement the approved spec contracts.

## Checks run
- `openspec validate real-bip32-vault-cryptography --strict` → pass
- `git rev-parse HEAD` → `f7523c317c5ae136da94422a1fe782af7d7a22ef`
- Read time: 6.0 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "real-bip32-vault-cryptography",
  "stage": "plan",
  "round": 1,
  "reviewer": "sdlc-plan-reviewer",
  "reviewed_sha": "f7523c317c5ae136da94422a1fe782af7d7a22ef",
  "verdict": "APPROVE",
  "summary": "Approved at Round 1: design and task breakdown comprehensively cover all bip32-cryptographic-vault and vault-simulation requirements with sound technical decisions, zero-overhead hot path preservation, strict fail-closed security, and verifiable dependency-ordered tasks.",
  "findings": [],
  "closed": []
}
```
