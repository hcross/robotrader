# Tasks — fix-policy-ttl-heartbeat

> Spec: [`specs/policy-ttl/spec.md`](specs/policy-ttl/spec.md). Proposal: [`proposal.md`](proposal.md). This list orders the work; the spec defines the contract.

## 1. Pin the defect with tests

- [x] 1.1 Create `backend/tests/test_policy_ttl_heartbeat.py` with an offline fake exchange (no network, no credentials) so `run_live_testnet_tick()` can be exercised, and assert that a successful tick leaves `issued_at_ms` and `ttl_seconds` unchanged. (covers: "A successful tick leaves the issue time unchanged")
- [x] 1.2 Add the early-return and raising-tick assertions: an unauthenticated tick, a tick with no active pod, and a tick whose exchange call raises all leave the active envelope unchanged. (covers: "An early-return tick leaves the issue time unchanged"; "A raising tick leaves the issue time unchanged")
- [x] 1.3 Add the repeated-tick assertion: ticking every 10 s across the TTL does not rewrite `issued_at_ms`, and at `T0 + 900_001` the effective policy is the safe baseline. (covers: "Repeated ticks cannot outlive the TTL")
- [x] 1.4 Add the liveness assertions: a liveness tick does not change `is_expired` or `get_effective_policy` for a fixed clock, liveness after expiry does not revive the envelope, `to_dict()` still emits exactly the six existing keys, and a post-tick persisted payload keeps its pre-change key set. (covers: "A liveness tick does not change the expiry verdict"; "Envelope wire shape is unchanged"; "Liveness after expiry does not revive the envelope"; "Liveness state does not alter the persistence shape")
- [x] 1.5 Add the boundary assertions: effective at exactly `T0 + ttl * 1000`, expired at `T0 + ttl * 1000 + 1`, with the same verdicts after any number of ticks. (covers: "The boundary instant is not expired"; "One millisecond after the boundary is expired"; "Tick count does not alter the boundary")
- [x] 1.6 Add restore tests with an injected fake Redis read: a fresh persisted envelope keeps its original `issued_at_ms`, `envelope_id`, and `ttl_seconds`; a persist-and-restore round trip preserves the issue time; a payload without `issued_at_ms` yields `safe_baseline_fallback`. (covers: "A fresh restored envelope keeps its original issue time"; "A persist-and-restore round trip preserves the issue time"; "A restored payload without an issue time is not fresh")
- [x] 1.7 Add stale-restore tests: an envelope past its TTL at restore time yields `safe_baseline_fallback` (`LOW_VOL_CARRY`, sniper disabled), is never served with the restore instant as its issue time, and the safe baseline TTL equals `SAFE_BASELINE_TTL_SECONDS` (900). (covers: "A stale restored envelope yields the safe baseline"; "A stale restore is not restamped as fresh"; "The safe baseline TTL comes from the shared contract")
- [x] 1.8 Add kill-switch tests covering active-over-fresh, active-over-expired, deactivation of an unexpired envelope, and deactivation after expiry. (covers: "Active kill switch overrides a fresh envelope"; "Active kill switch overrides an expired envelope"; "Deactivation restores an unexpired envelope"; "Deactivation after expiry yields the safe baseline")

## 2. Remove the live-worker renewal

- [x] 2.1 In `HybridStateStore.run_live_testnet_tick`, delete the block that assigns `self._policy.issued_at_ms = now_ms` and its comment; do not replace it with another write to the envelope. (covers: "Live ticks preserve policy issue time")
- [x] 2.2 If a liveness timestamp is retained, store it in dedicated `HybridStateStore` memory outside `PolicyEnvelope`, the persisted payload, and the REST/WS payloads, and never read it from expiry code; otherwise record no liveness state. (covers: "Liveness signals are separate from policy authority"; "Liveness state does not alter the persistence shape")
- [x] 2.3 Confirm `PolicyEnvelope.is_expired` and `HybridStateStore.get_effective_policy` are unchanged: strict `>` at the boundary, safe baseline when expired, kill switch first. (covers: "Expiry boundary semantics are unchanged")

## 3. Preserve issue time on restore

- [x] 3.1 In `HybridStateStore._load_persisted_state`, stop overwriting `issued_at_ms` with the restore instant. (covers: "A fresh restored envelope keeps its original issue time"; "A persist-and-restore round trip preserves the issue time")
- [x] 3.2 Detect a persisted policy object that omits `issued_at_ms` and start from `safe_baseline` instead of treating it as freshly issued. (covers: "A restored payload without an issue time is not fresh")
- [x] 3.3 Evaluate the restored envelope against its own TTL at the restore instant; when stale, make `safe_baseline` the effective policy without re-stamping the stale envelope. (covers: "A stale restored envelope yields the safe baseline"; "A stale restore is not restamped as fresh")
- [x] 3.4 Keep the safe-baseline TTL resolved from `SAFE_BASELINE_TTL_SECONDS`; add no independent TTL literal. (covers: "The safe baseline TTL comes from the shared contract")

## 4. Regression and boundary proof

- [x] 4.1 Run the existing `backend/tests/test_architecture.py` TTL test and the kill-switch path; confirm no expectation changed except the removed heartbeat. (covers: "Kill-switch behaviour is unchanged"; "Expiry boundary semantics are unchanged")
- [x] 4.2 Confirm no file under `engine-rs/` changed and no key was added to or removed from `PolicyEnvelope.to_dict()`. (covers: "Envelope wire shape is unchanged")
- [x] 4.3 Run the cross-language round-trip and single-source contract tests; confirm both pass with the unchanged wire shape. (covers: "Envelope wire shape is unchanged"; "The safe baseline TTL comes from the shared contract")

## Verification

- `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → expected: the Rust binary builds (prerequisite for the Python integration suite).
- `PYTHONPATH=. python3 -m unittest backend.tests.test_policy_ttl_heartbeat -v` → expected: every new test passes.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → expected: the full Python suite passes, including `test_architecture.py`, `test_contract_roundtrip.py`, and `test_contract_single_source.py`.
- `git diff --name-only origin/master...HEAD -- engine-rs` → expected: empty output.
- `openspec validate fix-policy-ttl-heartbeat --strict` → expected: the change validates.
- `scripts/sdlc/sdlc.sh check fix-policy-ttl-heartbeat` → expected: `check: PASS`.
