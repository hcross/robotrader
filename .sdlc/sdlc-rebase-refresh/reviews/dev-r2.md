# DEV Review — Round 2

## Summary
All Round 1 findings are closed or non-blocking. The mechanical-rebase paths are now documented in `sdlc/PROTOCOL.md` and the dev checklist, the invariant pack is derived from `openspec/config.yaml`, and new regression tests cover the rebase acceptance/refusal matrix. CI is green and the reviewed SHA matches the PR head; only two minor follow-ups remain.

## Findings

### DEV-R1-F01 — [major] Mechanical rebase paths are undocumented
- Location: `sdlc/PROTOCOL.md`; `sdlc/checklists/dev.md`
- Evidence: `grep -rn "refresh-sha\|mechanical" sdlc/ scripts/ openspec/` now matches `sdlc/PROTOCOL.md` (§7.5) and `sdlc/checklists/dev.md` (mechanical-rebase item).
- Required fix: Document both paths and add the checklist item.
- Status: closed
- Origin: initial

### DEV-R1-F02 — [minor] New CLI behavior has no tests
- Location: `scripts/sdlc/sdlc.py` (`cmd_refresh_sha`, `cmd_verdict --mechanical`)
- Evidence: `backend/tests/test_sdlc_rebase_refresh.py` exercises `_mechanical_rebase_ok` (faithful rebase, content change, merge shape, missing base) and the context pack; no direct CLI test for the missing-reason or non-ancestor refusals.
- Required fix: add a scripted CLI case for `refresh-sha` missing `--reason` and non-qualifying SHA.
- Status: open
- Origin: initial

### DEV-R1-F03 — [minor] Context-pack invariants are hardcoded
- Location: `scripts/sdlc/sdlc.py` (`build_brief`, `_invariants_from_config`)
- Evidence: `_invariants_from_config()` reads `openspec/config.yaml` and the brief consumes its output; `ContextPackTest` passes.
- Required fix: derive the invariant bullets from `openspec/config.yaml`.
- Status: closed
- Origin: initial

### DEV-R2-F04 — [minor] Context-pack invariant bullets are truncated
- Location: `scripts/sdlc/sdlc.py` (`_invariants_from_config`)
- Evidence: `python3 -c "import sdlc; print(sdlc._invariants_from_config())"` emits one line per physical YAML line, splitting multi-line invariants (e.g. "Zero LLM calls, blocking I/O, or unbounded sleeps in").
- Required fix: join wrapped continuation lines so each bullet is a complete invariant.
- Status: open
- Origin: regression

## Checks run
- `cd engine-rs && cargo test` → pass (all suites ok)
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → 241 tests run; 10 failures / 7 errors, all environment-related (missing `httpx` for `fastapi.testclient`); change-related `test_sdlc_rebase_refresh` → 5 passed
- `cd frontend && npm run build` → not run locally (`vite` not installed); CI `frontend` job pass
- `gh pr checks 209` → all pass (rust, python, frontend, helm, sdlc)
- `git diff --check` → no whitespace errors
- `scripts/sdlc/sdlc.sh check sdlc-rebase-refresh` → PASS

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "sdlc-rebase-refresh",
  "stage": "dev",
  "round": 2,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "ac91d6d7716c49ea732301efe839324df6a662e3",
  "verdict": "APPROVE",
  "summary": "Mechanical-rebase SHA refresh and context-pack briefs are implemented, documented, and CI-green; only non-blocking minor follow-ups remain.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "sdlc/PROTOCOL.md; sdlc/checklists/dev.md",
      "evidence": "sdlc/PROTOCOL.md §7.5 and the dev checklist now document refresh-sha/--mechanical and the mechanical-rebase verification item.",
      "required_fix": "Document both paths and add the checklist item."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "scripts/sdlc/sdlc.py (cmd_refresh_sha, --mechanical)",
      "evidence": "Tests cover _mechanical_rebase_ok and the context pack, but no direct CLI case for missing --reason or non-qualifying SHA.",
      "required_fix": "Add a scripted CLI case for refresh-sha missing --reason and non-qualifying SHA."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "scripts/sdlc/sdlc.py (build_brief, _invariants_from_config)",
      "evidence": "_invariants_from_config() reads openspec/config.yaml and ContextPackTest passes.",
      "required_fix": "Derive the invariant bullets from openspec/config.yaml."
    },
    {
      "id": "DEV-R2-F04",
      "severity": "minor",
      "origin": "regression",
      "status": "open",
      "location": "scripts/sdlc/sdlc.py (_invariants_from_config)",
      "evidence": "_invariants_from_config() emits one line per physical YAML line, splitting multi-line invariants.",
      "required_fix": "Join wrapped continuation lines so each bullet is a complete invariant."
    }
  ],
  "closed": [
    "DEV-R1-F01",
    "DEV-R1-F03"
  ]
}
```