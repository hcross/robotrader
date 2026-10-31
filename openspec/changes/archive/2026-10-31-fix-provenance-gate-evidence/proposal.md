# Change Proposal: Fix Provenance Gate Evidence

## Review Card (≤ 5 min)

| Field | Value |
|---|---|
| Outcome | Correct provenance grep-gate false positives, align UI fallback for unknown sources, and complete regression assertions. |
| Why now | DEV-R1 review on #15 flagged a comment tripping the `rust_leaf_backtest` gate, missing absence tests, and UI formatting drift. |
| Blast radius | `backend/core/provenance.py`, `backend/core/state_store.py`, `backend/tests/test_integrity_provenance.py`, `frontend/src/lib/provenance.js`. |
| Risk | Low; non-production test hardening and gate alignment. Worst failure: test failure in CI. |
| Effort | S, one review round. |
| Decision needed | None. |

```mermaid
flowchart LR
  A["Grep Gate False Positive & Review Nits (DEV-R1)"] --> B["Gate & Comment Fixes + Frontend Alignment"]
  B --> C["Automated Absence & Recursive Payload Assertions"]
  C --> D["Clean Grep Gates & Verified Provenance Integrity"]
```

### Non-goals
- No changes to Rust hot-path engine (`engine-rs`).
- No modification of Redis wire schemas or database structures.
- No changes to trading strategies, risk hurdles, or position sizing.

## Why

During the cold DEV review of change `fix-fabricated-metrics` (#15 / parent #7), several non-blocking evidence and guard hygiene findings were recorded (DEV-R1-F01 through DEV-R1-F05, plus PLAN-R2-F01). Specifically, the documented `rust_leaf_backtest` grep gate fails on its own explanatory comment in `backend/core/provenance.py`, and promised production absence tests were missing. Additionally, `formatMetric` formats numbers when supplied an unknown source while `badgeFor` marks them unattributed, and two spec scenarios lacked direct test assertions.

Addressing these hygiene findings now ensures the provenance gates are reliable and prevent regression across the test suite.

## What Changes

- **Provenance Grep Gate & Absence Tests**: Remove the literal `rust_leaf_backtest` token from the explanatory comment in `backend/core/provenance.py` so grep gates exit 1 cleanly. Add automated tests asserting that `rust_leaf_backtest` is absent from production modules (`backend/core`, `backend/agents`, `backend/server.py`), and that `solana_onchain_pnl_sol` and `simulated_model_pnl_usd` are absent from `backend/core/state_store.py`.
- **Frontend Metric Formatter Alignment**: Align `formatMetric` in `frontend/src/lib/provenance.js` with `badgeFor` by rendering `—` (em dash) for any unknown or non-enum source token, verified in `check-provenance.mjs`.
- **Evidence Recapture**: Replace the cropped `offline.png` in `.sdlc/fix-provenance-gate-evidence/evidence/` with a full-viewport screenshot capturing the header's `OFFLINE` badge and timestamp.
- **Test Suite Completeness**: Implement a recursive traversal test in `backend/tests/test_integrity_provenance.py` asserting that all numeric performance values in `/api/v1/status` declare an attributed enum source. Add direct test assertions for JSONL-only drawer persistence without Redis, and for the bootstrap-only continuity prompt message.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `integrity`: Clarifies provenance alignment for unknown sources in UI rendering, enforces production absence of deprecated producer and model tokens, and adds explicit test assertions for recursive payload validation, JSONL-only drawer round-trips, and bootstrap-only prompt messaging.

## Non-goals

- No new endpoints or public contract modifications.
- No changes to live order routing, execution logic, or Rust crates.
- No modifications to Redis state persistence mechanisms or telemetry schemas.
- No alteration of `CostGuard` accounting or OpenRouter credit refills.

## Impact

- **Code modules**: `backend/core/provenance.py`, `backend/core/state_store.py`, `frontend/src/lib/provenance.js`.
- **Test & Validation scripts**: `backend/tests/test_integrity_provenance.py`, `frontend/scripts/check-provenance.mjs`.
- **Evidence**: `.sdlc/fix-provenance-gate-evidence/evidence/offline.png`.
- **APIs and Contracts**: Internal hardening only; no breaking changes to API endpoints or schemas.
