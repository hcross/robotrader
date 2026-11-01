# DEV Review — Round 1

## Summary

The change adds BNB Chain leaf TA metrics computation and market snapshot ingestion in `backend/tools/ta_tools.py`, mirroring the existing Sui/Ethereum/Hyperliquid pattern, plus dedicated unit tests. Only the two expected files changed. No contract, risk-gate, vault, or frontend surface is touched. Rust and Python suites pass locally and all GitHub PR checks are green; the Docker backend image builds. The implementation covers all six required metrics and the fallback path expected by tests. Approved.

## Findings

(none)

## Checks run

- `cd engine-rs && cargo test` → PASS (all crates: 59+ tests, 0 failures)
- venv Python `PYTHONPATH=. python3 -m unittest discover -s backend/tests` → PASS (292 tests, 0 failures). System `python3` lacks ccxt/httpx; the canonical poetry venv reproduces CI.
- `cd frontend && npm run build` → N/A (no frontend files changed; local node_modules absent; CI `frontend` check PASS)
- `docker compose --env-file .env.example build backend` → PASS (backend image built)
- `gh pr checks 197` → PASS (rust, python, frontend, helm)

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-bnb-ingestion",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "3e679b1b391e37b8a314f995f4b950a4788b9211",
  "verdict": "APPROVE",
  "summary": "BNB leaf TA metrics and ingestion landed with tests; no invariant or contract impact; all required checks pass.",
  "findings": [],
  "closed": []
}
```