# DEV Review Checklist (Robotrader)

> Read after `sdlc/PROTOCOL.md`, the approved SPEC (and PLAN for Lane L), and the PR diff.
> Run the code yourself. Do not trust the author's logs.

## 0. Scope

- [ ] The diff implements only the approved spec/plan.
- [ ] No unrelated refactor, formatting sweep, or dependency bump rides along.
- [ ] The diff matches the PR description and the issue logbook.
- [ ] No generated artifacts, secrets, or local data are committed.

## 1. Correctness

- [ ] Every changed behavior maps to a scenario or invariant.
- [ ] Error paths return a correct, typed failure; no silent `unwrap`/broad `except`.
- [ ] Boundary conditions are handled (empty, zero, negative, overflow, partial fill).
- [ ] Concurrency: no data race, lock-order inversion, or unbounded queue.
- [ ] Time and units are explicit (ms/µs, bps, seconds, decimals vs floats).

## 2. Robotrader hard invariants

- [ ] Zero LLM calls, blocking I/O, or unbounded sleeps in `StrategyPod::on_market_event` or `HardRiskGate::validate`.
- [ ] `HardRiskGate::validate` stays within the 50µs budget; no allocation or logging on that path.
- [ ] `PolicyEnvelope` remains synchronized between `engine-rs/crates/common/src/lib.rs` and `backend/core/schemas.py`, including every `AssetOverride` field.
- [ ] Capital protection is intact: dry powder ≥ 20%, Kelly sizing, drawdown kill-switch, `CostGuard` daily cap.
- [ ] No unbounded wallet or credit refill is reintroduced.
- [ ] The vault is labelled `SIMULATED` at every surface (`SimulatedVault`, manifest, receipt, UI): `simulated: true`, `address_is_spendable: false`, `signature_is_chain_valid: false`, `whitelist_enforcement: "SIMULATED"`.
- [ ] Python holds no key custody: no seed read, no signing keypair, no fabricated manifest or signature, and no Solana broadcast.
- [ ] `destination_whitelisted` and `key_zeroized_after_sign` are derived from the actual call, not compile-time literals.
- [ ] No docstring, comment, test name, or document claims real derivation, chain-valid signing, or mainnet custody; no key material in logs/evidence.
- [ ] Backtest == paper == live: the same deterministic code path; no look-ahead or live-only branch in strategy logic.
- [ ] Each leaf robot stays isolated to its chain/venue and its MemPalace wing.
- [ ] `backend/core/` still holds warm-path infrastructure; `import strands` is not shadowed.

## 3. Contracts and compatibility

- [ ] Rust/Python schemas agree field-for-field, including optionality and defaults.
- [ ] Redis IPC keys, TTLs, and payload shapes are backward compatible or versioned.
- [ ] REST/WS changes are documented and the frontend still builds.
- [ ] Serialization has no precision loss (decimals, timestamps, enums).
- [ ] Existing consumers are updated or the change is additive.

## 4. Security

- [ ] Inputs crossing trust boundaries are validated (RPC, exchange, RSS, user input).
- [ ] No secret, private key, API token, or production address in code, logs, fixtures, or tests.
- [ ] On-chain safety checks are not bypassed (`OnChainTokenSafety`, honeypot, LP lock).
- [ ] Dependencies are pinned and have no known critical advisory.
- [ ] File/network access follows least privilege.

## 5. Tests and evidence

- [ ] New behavior has a test or a documented verification that would fail without the change.
- [ ] Negative and boundary tests exist where the risk warrants it.
- [ ] Tests are deterministic: no wall-clock, network, or random dependence without a seed.
- [ ] The reviewer ran the relevant commands and captured the output.
- [ ] For hot-path changes: a benchmark or latency measurement is attached.
- [ ] For backend/frontend changes: `docker compose up --build -d` was run and the service is reachable.
- [ ] For a mechanical rebase: the commits carrying `[<change-id>]` keep the same
      `git patch-id` before and after the rebase, and no new file appears in the diff.
- [ ] For UI changes: a screenshot or recording is attached.

### Canonical commands

```bash
cd engine-rs && cargo test
PYTHONPATH=. python3 -m unittest discover -s backend/tests -v
cd frontend && npm run build
docker compose up --build -d        # backend/frontend changes
```

## 6. Performance and cost

- [ ] No new per-tick allocation, clone, or `format!` in the hot path.
- [ ] Complexity is bounded and documented for new loops.
- [ ] LLM calls are on the warm path, budgeted by `CostGuard`, and timeout-bounded.
- [ ] New schedulers are off by default and costed in the PR.

## 7. Maintainability

- [ ] Names describe the domain, not the implementation.
- [ ] Errors carry context; no swallowed error.
- [ ] No dead code, commented-out block, or debug print.
- [ ] The change reads like the surrounding code (style, comment density, idiom).
- [ ] Public APIs have a doc comment where the contract is non-obvious.

## 8. Operations

- [ ] Config is documented with safe defaults.
- [ ] Observability is adequate: logs/metrics for the new path.
- [ ] Rollback is possible without a data restore.
- [ ] No migration runs implicitly on startup without a guard.

## Verdict rules

- `blocker`: invariant violation, unsafe money/risk/vault behavior, contract break, missing test for a claimed behavior, failing CI.
- `major`: correctness defect in a non-critical path, missing failure handling, unverifiable claim.
- `minor`: maintainability, naming, missing non-critical test.
- `nit`: style.
- `APPROVE` requires zero open blocker/major, all required checks run, and the reviewed SHA equal to the PR head.
