stage: dev
round: 1
head_sha: d5ba55f88a4a2b9fe559506cf4c8c30a3d9073c7
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: "engine-rs/crates/exec-router/src/lib.rs XrpVenueAdapter::validate_settlement_destination now accepts only bridge:xrpl:/bridge:ripple: prefixes with a non-empty suffix, or an r-prefixed XRPL classic address that is 33-34 characters total (32-33 after r) using the Ripple base58 alphabet. Validated by cargo test (exec-router 59 + isolation tests ok), PYTHONPATH=. python3.11 unittest discover backend/tests (306 tests OK), and frontend npm build (PASS)."
