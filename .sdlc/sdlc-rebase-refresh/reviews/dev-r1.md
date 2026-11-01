# DEV Review — Round 1

## Summary
The implementation adds `refresh-sha` and a `--mechanical` verdict path with correct ancestor gating, plus a context pack in generated briefs. Core behavior matches the issue's contract and the CLI runs. The gap is documentation: `sdlc/PROTOCOL.md` and `sdlc/checklists/dev.md` were not updated to document the new paths or the mechanical-rebase review item, despite both being explicit deliverables. Two minor follow-ups on test coverage and invariant drift.

## Findings

### DEV-R1-F01 — [major] Mechanical rebase paths are undocumented
- Location: `sdlc/PROTOCOL.md`; `sdlc/checklists/dev.md`
- Evidence: `grep -rn "refresh-sha\|mechanical" sdlc/ scripts/ openspec/` returns matches only in `scripts/sdlc/sdlc.py`; PR diff stat shows 3 changed files, none of the two docs.
- Required fix: Document `sdlc.py refresh-sha <change> <stage> --sha <sha> --reason "<text>"` and `sdlc.py verdict ... --mechanical` in `sdlc/PROTOCOL.md`, and add a checklist item to `sdlc/checklists/dev.md` requiring verification that the rebase delta is conflict resolution only.
- Status: open
- Origin: initial

### DEV-R1-F02 — [minor] New CLI behavior has no tests
- Location: `scripts/sdlc/sdlc.py` (`cmd_refresh_sha`, `cmd_verdict --mechanical`)
- Evidence: no files under `backend/tests` or `scripts/sdlc/tests` exercise `refresh-sha` or `--mechanical`; PR adds no test.
- Required fix: add at least one scripted/CLI verification covering the refuse-on-missing-reason and refuse-on-non-ancestor cases.
- Status: open
- Origin: initial

### DEV-R1-F03 — [minor] Context-pack invariants are hardcoded
- Location: `scripts/sdlc/sdlc.py` (`build_brief`, context pack block)
- Evidence: the invariant bullets are string literals; `openspec/config.yaml` is not read at brief-build time.
- Required fix: derive the invariant bullets from `openspec/config.yaml` (or document why a static copy is authoritative) to prevent drift.
- Status: open
- Origin: initial

## Checks run
- `cargo test` (engine-rs) → pass (all suites ok)
- `python3 -m py_compile scripts/sdlc/sdlc.py scripts/sdlc/common.py` → pass
- `python3 -m unittest discover -s backend/tests -v` → 236 tests, 10 failures / 7 errors, all environment-related (missing `dotenv`, `ccxt`, `httpx`; no change-related regression)
- `cd frontend && npm run build` → not run (node_modules absent; no frontend files changed)
- `gh pr checks 209` → sdlc pass
- `git diff --check` → no whitespace errors

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "sdlc-rebase-refresh",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "51d5cce4171b04cbce9fe058872418267c969b34",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Mechanical rebase paths are undocumented in PROTOCOL.md and the dev checklist.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "sdlc/PROTOCOL.md; sdlc/checklists/dev.md",
      "evidence": "grep found refresh-sha/--mechanical only in scripts/sdlc/sdlc.py; PR diff touches 3 files, none are the two docs.",
      "required_fix": "Document both paths in PROTOCOL.md and add a mechanical-rebase verification item to sdlc/checklists/dev.md."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "scripts/sdlc/sdlc.py (cmd_refresh_sha, --mechanical)",
      "evidence": "No tests exercise refresh-sha or --mechanical.",
      "required_fix": "Add scripted verification for missing-reason and non-ancestor refusals."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "scripts/sdlc/sdlc.py (build_brief context pack)",
      "evidence": "Invariant bullets are string literals; openspec/config.yaml is not read at brief-build time.",
      "required_fix": "Derive the invariant bullets from openspec/config.yaml or document the static copy as authoritative."
    }
  ],
  "closed": []
}
```