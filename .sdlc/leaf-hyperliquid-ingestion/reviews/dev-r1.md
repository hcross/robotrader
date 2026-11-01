# DEV Review — Round 1

## Summary
Diff adds Hyperliquid TA metrics helpers and tests in `backend/tools/ta_tools.py`, mirroring the existing Sui/Ethereum pattern. New hyperliquid test passes; Rust and core Python suite behavior is unchanged aside from pre-existing/environmental failures reproduced identically on the base SHA. No invariants, contracts, or hot-path budget affected. One non-blocking minor edge case noted.

## Findings

### DEV-R1-F01 — [minor] Hyperliquid fallback can emit `obi_l2=0.0` when only one side of the order book is supplied
- Location: `backend/tools/ta_tools.py:613-622` (fallback branch `obi_l2` handling)
- Evidence: Fallback uses `obi if (bids or asks) else ...` but `obi` stays `0.0` unless both `bids` and `asks` are truthy, because the computation is guarded by `if bids and asks:` at lines 604-610. With only asks (or only bids) supplied, a supplied empty-ish side collapses to `0.0` instead of the configured fallback `0.27`.
- Required fix: Guard the fallback with the same `bids and asks` condition used for computation, or leave the behavior to match the Sui/Ethereum peers; either way, add a boundary assertion only if the maintainer wants strictness.
- Status: open
- Origin: initial

## Checks run
- `cd engine-rs && cargo test` → all suites pass (59+18+... tests; 0 failures)
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → 17 failures/errors, identical to base SHA e.g. missing `httpx2`/`starlette.testclient`, `ccxt`, env-only; new Hyperliquid test passes.
- `cd frontend && npm run build` → not run: `node_modules` absent in worktree; no frontend files changed by this diff.
- `gh pr checks 195` → all pass (frontend 10s, helm 7s, python 51s, rust 21s).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-hyperliquid-ingestion",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "e42eccbc55c6a9665131c3d5f4a8912e699cab7b",
  "verdict": "APPROVE",
  "summary": "Hyperliquid TA helpers and tests are consistent with peers; no blockers or majors; required targeted tests pass.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/tools/ta_tools.py:613-622",
      "evidence": "Fallback uses obi if (bids or asks) else ... while obi stays 0.0 unless both bids and asks are supplied.",
      "required_fix": "Align the fallback condition with the bids-and-asks computation guard for one-sided books."
    }
  ],
  "closed": []
}
```