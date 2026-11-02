stage: dev
round: 1
head_sha: 2c7e4a2b09dd9314d1a7f6572c52919d4389fb17
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: "Replaced router bech32 charset with vault charset (qpzry9x8gf2tvdw0s3jn54khce6mua7l) in engine-rs/crates/exec-router/src/lib.rs CosmosVenueAdapter::validate_settlement_destination; added positive test with 4/6-containing vault-style address and negative test for 'b'."
  - id: DEV-R1-F02
    action: fixed
    evidence: "Enforced rest.len() == 38 (total 45) for cosmos1 addresses; added regression tests for 37/39 lengths and rejection of the old 36-char sample."
  - id: DEV-R1-F03
    action: fixed
    evidence: "PR #234 body regenerated with change id leaf-cosmos-execution-custody and issue #86 (gh pr edit)."
  - id: DEV-R1-F04
    action: fixed
    evidence: "Aligned SUPPORTED_TOKENS with the isolation gate token set: ATOM, USDC, OSMO, INJ."
