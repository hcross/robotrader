# DEV Review — Round 1

## Summary
Reviewed the two-file TON RSS/catalyst ingestion change at `e8112f27`. The change mirrors the established leaf pattern and CI is green, but venue extraction in `score_ton_catalyst` classifies DeDust items as `TON_STONFI_DEX` whenever generic DEX tokens such as "swap" or "liquidity pool" appear, because the STON.fi branch is evaluated before the DeDust branch. This breaks venue-specific catalyst categorization and must be corrected before approval.

## Findings

### DEV-R1-F01 — [major] DeDust catalysts miscategorized as STON.fi due to generic-keyword precedence
- Location: `backend/tools/rss_tools.py:887-890`
- Evidence: `EcosystemRSSAggregator.score_ton_catalyst("DeDust liquidity pool surge", "")` returns `category='TON_STONFI_DEX'` and `score_ton_catalyst("DeDust swap growth", "")` likewise returns `TON_STONFI_DEX` instead of `TON_DEDUST_DEX`, because the first branch matches shared tokens (`"swap"`, `"liquidity pool"`) before the DeDust venue branch is reached.
- Required fix: evaluate DeDust-specific terms (`"dedust"`, `"de dust"`, `"dedust.io"`) before the STON.fi/generic DEX terms (or remove the shared generic tokens from the STON branch), matching the venue-first ordering used by the SUI scorer.
- Status: open
- Origin: initial

## Checks run
- `cd engine-rs && cargo test` → PASS (all crates; 0 failures)
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → 233 tests run, 10 failures + 7 errors, identical to the base SHA failure set (environmental: missing `ccxt` / node-binary paths / unset control-plane token); `test_ton_rss_atom_parsing_and_catalyst_scoring` passes when run in isolation (1 pass)
- `cd frontend && npm run build` → NOT RUN in this worktree (no frontend changes; `node_modules` absent)
- `docker compose up --build -d` → images built successfully; startup blocked by host port `6379` already allocated by `robotrader-redis-1` (pre-existing container)
- `gh pr checks 203` → PASS (rust, python, frontend, helm)

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-ton-rss-catalysts",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "e8112f27fc1fb94963988df7fb9044fba0a2d39a",
  "verdict": "CHANGES_REQUESTED",
  "summary": "TON RSS/catalyst ingestion mirrors the established leaf pattern, but DeDust items are miscategorized as STON.fi because generic DEX keywords are matched first; fix venue precedence.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/tools/rss_tools.py:887-890",
      "evidence": "score_ton_catalyst('DeDust liquidity pool surge', '') returns category 'TON_STONFI_DEX' instead of 'TON_DEDUST_DEX' because shared tokens ('swap', 'liquidity pool') are tested before the DeDust venue branch.",
      "required_fix": "Evaluate DeDust-specific terms before STON.fi/generic DEX terms (or remove shared generic tokens from the STON branch), matching venue-first ordering used by the SUI scorer."
    }
  ],
  "closed": []
}
```
