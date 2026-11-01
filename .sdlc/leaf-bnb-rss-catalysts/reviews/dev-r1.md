# DEV Review — Round 1

## Summary

Lane M change restricted to two files: `backend/tools/rss_tools.py` (additive BNB Chain catalyst scorer + feed ingestion + dispatch hooks) and a parser regression test in `backend/tests/test_hierarchy_v3.py` (atom + RSS + curated fallback). Hot path untouched, no PolicyEnvelope/contract change, leaf isolation preserved (`BNB_EXCLUSIVE_ASSETS`). All required checks pass (`cargo test`, 297 Python tests incl. new test, frontend build, `gh pr checks` green). Docker build succeeded; runtime `up` blocked only by a pre-existing port-6379 conflict, not by this change. Verdict: APPROVE.

## Findings

### DEV-R1-F01 — [minor] Duplicate module-level `if __name__ == "__main__"` guard appended
- Location: `backend/tests/test_hierarchy_v3.py:1729`
- Evidence: the commit appended a second `if __name__ == "__main__": unittest.main()` block at the end of the file, immediately before the existing one at line 1677; both guards are harmless and both execute only when run as a script.
- Required fix: remove the redundant trailing guard to keep the file tidy. Non-blocking follow-up.
- Status: open
- Origin: initial

### DEV-R1-F02 — [nit] Empty-bytes feed payload is treated as missing
- Location: `backend/tools/rss_tools.py:verify_and_ingest_bnb_feeds` (`xml_payloads.get(...) or ...`)
- Evidence: an empty-bytes payload is falsy, so ingestion falls back to curated fixtures instead of parsing an empty feed (same behavior as the sibling SUI/XRP implementations).
- Required fix: none required for parity; if stricter semantics are desired, switch to `is None` checks. Non-blocking follow-up.
- Status: open
- Origin: initial

## Checks run

- `cargo test` (engine-rs) → pass (all suites, 0 failures)
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests` → `Ran 297 tests in 14.6s, OK` (incl. `test_bnb_rss_atom_parsing_and_catalyst_scoring`)
- `cd frontend && npm run build` → pass
- `docker compose up --build -d` → images built; runtime blocked by port 6379 already allocated by existing stack (unrelated to change)
- `gh pr checks 205` → rust/python/frontend/helm all pass

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-bnb-rss-catalysts",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "472f82157ce614de3dd8ca99405efd790d284060",
  "verdict": "APPROVE",
  "summary": "Additive BNB Chain RSS/Atom catalyst scoring and ingestion; tests pass; no invariant violated.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_hierarchy_v3.py:1729",
      "evidence": "Second trailing `if __name__ == \"__main__\": unittest.main()` appended after the existing guard.",
      "required_fix": "Remove the redundant trailing guard; non-blocking."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tools/rss_tools.py:verify_and_ingest_bnb_feeds",
      "evidence": "Empty-bytes payload collapses to curated fallback via `or`.",
      "required_fix": "None required for parity; optionally use `is None` checks."
    }
  ],
  "closed": []
}
``` 
Now need to check whether including minor/nit as "findings" with open status might violate APPROVE? Rule: APPROVE iff zero open blocker/major. Minor ok. But some verdict linters might expect findings array only blockers/majors? The schema allows findings. Fine.

Let me also remove the .env (done) to keep clean. Need ensure no uncommitted changes besides verdict. Let me check git status.