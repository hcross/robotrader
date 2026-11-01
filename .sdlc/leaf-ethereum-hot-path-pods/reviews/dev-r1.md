```yaml
schema: sdlc.verdict/v1
change_id: leaf-ethereum-hot-path-pods
stage: dev
round: 1
reviewer: sdlc-dev-reviewer
reviewed_sha: f9bba3b2b957f0b2e4b6eae74793d9088c7392c8
verdict: CHANGES_REQUESTED
summary: PR #190 fails compilation during strategy tests due to an invalid field name `pool_address` on `MarketEvent::OnchainPoolLaunch`.
findings:
  - id: DEV-R1-F01
    severity: blocker
    origin: initial
    status: open
    location: engine-rs/crates/strategies/src/lib.rs:1349
    evidence: "cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-strategies failed with E0559: variant robotrader_common::MarketEvent::OnchainPoolLaunch has no field named pool_address"
    required_fix: "Replace pool_address with token_address (matching MarketEvent::OnchainPoolLaunch definition) in test_leaf_ethereum_pods_asset_isolation_and_erc20_safety."
closed: []
```

<DEV Review — Round 1>
## Summary
PR #190 ("leaf-ethereum-hot-path-pods", Issue #37, Lane M) implements Ethereum leaf pods, asset isolation, and ERC20 token safety verification. However, `cargo test` fails compilation because `MarketEvent::OnchainPoolLaunch` in the test suite uses `pool_address` instead of `token_address`. Changes requested.

## Findings

### DEV-R1-F01 — [blocker] Invalid field name on MarketEvent::OnchainPoolLaunch in test suite
- Location: `engine-rs/crates/strategies/src/lib.rs:1349`
- Evidence: `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-strategies` fails with `error[E0559]: variant robotrader_common::MarketEvent::OnchainPoolLaunch has no field named pool_address`.
- Required fix: Replace `pool_address` with `token_address` in `test_leaf_ethereum_pods_asset_isolation_and_erc20_safety`.
- Status: open
- Origin: initial

## Checks run
- `cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-strategies` → FAILED (E0559 compilation error)
- `git diff origin/master...HEAD` → Verified modifications are confined to `engine-rs/crates/strategies/src/lib.rs`.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-ethereum-hot-path-pods",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "f9bba3b2b957f0b2e4b6eae74793d9088c7392c8",
  "verdict": "CHANGES_REQUESTED",
  "summary": "PR #190 fails compilation during strategy tests due to an invalid field name `pool_address` on `MarketEvent::OnchainPoolLaunch`.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "blocker",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/strategies/src/lib.rs:1349",
      "evidence": "cargo test --manifest-path engine-rs/Cargo.toml -p robotrader-strategies failed with E0559: variant robotrader_common::MarketEvent::OnchainPoolLaunch has no field named pool_address",
      "required_fix": "Replace pool_address with token_address (matching MarketEvent::OnchainPoolLaunch definition) in test_leaf_ethereum_pods_asset_isolation_and_erc20_safety."
    }
  ],
  "closed": []
}
```
</DEV Review — Round 1>
