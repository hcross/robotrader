# DEV Review — Round 1

## Summary

APPROVE at `a9718e4d72a550ab65f5263c65f89d2875648c6a`. The diff implements the approved spec/design: one provenance vocabulary, nullable leaf performance split by population, treasury aggregation from measured rows only, fail-closed `BOOTSTRAP` drawers excluded from prompts, null-safe refill without the `$125` floor, and em-dash rendering with badges. I ran the shipped suite (103 tests, OK with 9 skipped), Rust tests, frontend build, the provenance script and node assertions, OpenSpec/SDLC checks, and reproduced the lint baseline (same five pre-existing errors as `master`); CI is green and the PR head equals the reviewed SHA. One minor evidence/tooling finding (a documented grep gate is tripped by its own explanatory comment, and the design's production-absence test is absent) plus four follow-up nits; none blocks. The minor must be corrected before merge-ready.

## Checklist walk

| Section | Result | Evidence |
|---|---|---|
| 0. Scope | PASS | 18 non-ledger files, +2093/−258; no `engine-rs/`, dependency, Dockerfile, Compose, Helm or `PolicyEnvelope` change; spec/design/proposal identical between `fd9eff5` and head (only `tasks.md` checkboxes changed). |
| 1. Correctness | PASS | Nullable/empty/zero/one-row/eviction paths tested in `backend/tests/test_integrity_provenance.py`; refill null-safe; no broad `except` added beyond the design-mandated best-effort Redis compaction. |
| 2. Robotrader invariants | PASS | Hot path, `HardRiskGate`, `PolicyEnvelope` parity, capital protection, vault, chain isolation untouched; #9 503 handler/resolver unchanged and `test_missing_binary` passes. |
| 3. Contracts | PASS | `contract_version: 2`; enum `source` + `source_detail`; flat leaf keys removed; only consumer (`frontend/`) updated in the same diff. |
| 4. Security | PASS | No secret/key/token in code, tests, docs or evidence; vault-manifest fallback (#7.3) deliberately untouched. |
| 5. Tests and evidence | PASS (nits F02/F05) | Every claimed behaviour has a test; screenshots present and consistent; `get_population_metrics` cost measured in the image at 0.5–0.8 ms, so the extra leaf-endpoint call is not material. |
| 6. Performance and cost | PASS | No hot-path or scheduler change; refill gate strictly stricter; no new per-tick work. |
| 7. Maintainability | PASS | Single `backend/core/provenance.py`; docstrings on helpers; no debug prints or dead branches. |
| 8. Operations | PASS | Rollback in PR body matches the live key names; Redis compaction is guarded and correctness does not depend on it. |

## Findings

### DEV-R1-F01 — [minor] The documented `rust_leaf_backtest` production grep gate fails, and the design's absence test is missing
- Location: `backend/core/provenance.py:24` (comment); `openspec/changes/fix-fabricated-metrics/tasks.md:101`; PR #15 body, "Grep gates (all exit 1, expected)".
- Evidence: `git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py` exits 0 with `backend/core/provenance.py:24:# \`rust_leaf_backtest\` is deliberately absent: ...`, while the task's verification expects exit 1. `grep -rn 'rust_leaf_backtest' backend/tests` shows only the two mapping assertions (`:128`, `:131`), so design D4's "A test asserts the producer token is absent from production modules" is also unimplemented. The runtime behaviour is sound: `execution_rows_source` rejects the token, and both leaf branches assert `executions_source == "backtest_fixture"`.
- Required fix: Remove the literal token from the comment (e.g. "the per-leaf replay producer token") so the gate exits 1, and either add the design-promised absence test or record the deviation in `tasks.md`/the PR body; correct the claim that all grep gates exit 1.
- Status: open
- Origin: initial

### DEV-R1-F02 — [nit] Task 8.1's "recursive payload test" is implemented as enumerated assertions
- Location: `backend/tests/test_integrity_provenance.py:1071-1099` (`ServerPayloadTests`, child script `:981-1065`).
- Evidence: The scenario child asserts specific paths (`contract_version`, the three `engine_metrics` sources, row sources, leaf sub-block sources, treasury, telemetry, drawers) but performs no recursive walk; a future numeric performance key added without a `source` would not be caught, which is exactly what task 8.1 says the test asserts.
- Required fix: Add a recursive traversal of the status payload that rejects any numeric performance field without an enum source (or amend task 8.1 to say the test is enumerated).
- Status: open
- Origin: initial

### DEV-R1-F03 — [nit] `offline.png` does not show the `OFFLINE` badge/timestamp claimed for it
- Location: `.sdlc/fix-fabricated-metrics/evidence/offline.png` (1504×1135) vs PR #15 body, "Behavioural screenshots" table.
- Evidence: The image shows the degraded skeleton (empty leaf list, all treasury tiles `—`), but it is cropped below the header, so the `OFFLINE — last success HH:MM:SS` badge is not in frame. The code path is correct (`frontend/src/App.jsx:240` renders it when `offlineSince && lastSuccessAt`), so this is evidence completeness, not behaviour.
- Required fix: Attach a capture that includes the header badge, or amend the PR body to describe the crop accurately.
- Status: open
- Origin: initial

### DEV-R1-F04 — [nit] `formatMetric` renders a number for an unknown source while the badge reads `UNATTRIBUTED`
- Location: `frontend/src/lib/provenance.js:29-31` (`badgeFor`) and `:57-62` (`formatMetric`).
- Evidence: `node --input-type=module -e '...'` prints `formatMetric(10,BOGUS)= "$10.00" badgeFor(BOGUS)= UNATTRIBUTED`. An `UNATTRIBUTED` badge beside a rendered number contradicts the D12 gate. Not reachable from the shipped backend (all served sources are normalised), hence nit.
- Required fix: Treat any source outside `METRIC_SOURCES`/`DRAWER_SOURCES` like `null` in `formatMetric` (return `—`) and add the corresponding assertion to `check-provenance.mjs`.
- Status: open
- Origin: initial

### DEV-R1-F05 — [nit] Two explicit spec scenarios are not directly asserted
- Location: `backend/tests/test_integrity_provenance.py:548-609` and `:629-668`.
- Evidence: (a) no test builds the continuity prompt on a bootstrap-only palace to assert the "Aucune thèse antérieure..." message required by "Bootstrap drawers are absent from the continuity prompt"; `test_prompts_exclude_bootstrap_and_filter_before_limit` always adds an eligible `LLM` drawer. (b) `test_bootstrap_append_survives_jsonl_and_redis_round_trip` reloads with Redis configured, and `memory_palace.py:101-109` consults Redis first, so the JSONL half of "Drawer source survives persistence" is not exercised for a new `BOOTSTRAP` drawer.
- Required fix: Add the bootstrap-only prompt assertion and a JSONL-only reload assertion (construct the second palace without `redis_cmd_fn`).
- Status: open
- Origin: initial

## Checks run

- `docker build -f Dockerfile.backend -t robotrader-backend:integrity-review .` → exit 0.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:integrity-review python -m unittest discover -s backend/tests -v` → `Ran 103 tests in 7.301s`, `OK (skipped=9)`, exit 0.
- `cd engine-rs && cargo test --all-targets` → exit 0; suite results `2/1/14/0/0/5/0/18 passed`, 0 failed.
- `cd frontend && npm run build` → exit 0, `✓ built in 467ms`.
- `cd frontend && node scripts/check-provenance.mjs` → `provenance wiring OK`, exit 0.
- D12 node assertions (`formatMetric`/`formatOperational`/`badgeFor`) → `provenance helper OK`, exit 0.
- `cd frontend && npm run lint` → exit 1, `5 problems (5 errors)`; each reproduced on `master` via `git show master:frontend/<file> | npx eslint --stdin` (App `set-state-in-effect`, Dashboard unused `Icon`, three MasterOverview unused vars). Zero new errors.
- `openspec validate fix-fabricated-metrics --strict` → `Change 'fix-fabricated-metrics' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check fix-fabricated-metrics` → `check: PASS`; `tasks: 56 done, 0 open`; spec-lint PASS; verdict-lint PASS.
- Grep gates: G1 (`2.45|64.5|alloc_usd * 0.0xx`), G2 (`tokens_used=1420|620|cost_usd=0.00048`), G4 (`max(125.0`), G5 (`float(lf.get("realized_pnl_usd"`), G6 (`simulated_model_pnl_usd`), G7 (`solana_onchain_pnl_sol`), G8 (UI defaults) → all exit 1. G3 (`rust_leaf_backtest` in production modules) → exit 0 at `backend/core/provenance.py:24` (finding F01).
- `gh pr checks 15` → frontend pass, helm pass, python pass, rust pass, sdlc pass.
- `gh pr view 15 --json isDraft,headRefOid,mergeable` → `isDraft: true`, `headRefOid: a9718e4d72a550ab65f5263c65f89d2875648c6a`, `mergeable: MERGEABLE`.
- `git diff --name-only master...a9718e4 -- engine-rs frontend/package.json frontend/package-lock.json backend/pyproject.toml backend/poetry.lock Dockerfile.backend docker-compose.yml charts` → empty.
- `git diff --stat fd9eff5..a9718e4 -- openspec/changes/fix-fabricated-metrics` → only `tasks.md` (56 checkbox lines), spec/design/proposal unchanged.
- Evidence inspected: `status-payload.json` (contract 2, enum sources, null leaf metrics, `BOOTSTRAP` drawer with empty telemetry), `leaf-detail.txt`, `refill-smoke.json` (`rejected_no_realized_profit`, `$0.00`), and all five screenshots (`leaf-null.png` and `bootstrap-drawer.png` show `—` + `MEASURED`/`SIMULATED`/`BOOTSTRAP` correctly; `offline.png` crop caveat in F03).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-fabricated-metrics",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "a9718e4d72a550ab65f5263c65f89d2875648c6a",
  "verdict": "APPROVE",
  "summary": "The diff implements the approved provenance contract end to end and every required check passes at the PR head; one minor evidence/tooling finding and four nits remain, none blocking.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/core/provenance.py:24; openspec/changes/fix-fabricated-metrics/tasks.md:101; PR #15 grep-gate claim",
      "evidence": "git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py exits 0 on the comment at provenance.py:24, while tasks.md expects exit 1; no production-absence test exists despite design D4. Runtime rejection and both leaf-branch assertions make the behaviour sound.",
      "required_fix": "Remove the literal token from the comment or amend the gate, add the design-promised absence test (or record the deviation), and correct the PR body claim that all grep gates exit 1."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_integrity_provenance.py:1071-1099",
      "evidence": "Task 8.1 promises a recursive payload test; the child script asserts enumerated paths only, so a future numeric performance key without a source would not be caught.",
      "required_fix": "Add a recursive payload traversal rejecting numeric performance values without an enum source, or amend task 8.1 to describe the enumerated test."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": ".sdlc/fix-fabricated-metrics/evidence/offline.png vs PR #15 behavioural-screenshot claim",
      "evidence": "The screenshot shows the degraded skeleton but is cropped below the header, so the OFFLINE badge/timestamp is not visible; frontend/src/App.jsx:240 implements it correctly.",
      "required_fix": "Attach a capture including the header badge, or amend the evidence description."
    },
    {
      "id": "DEV-R1-F04",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "frontend/src/lib/provenance.js:29-31 and :57-62",
      "evidence": "formatMetric(10,'BOGUS','money') returns '$10.00' while badgeFor('BOGUS') returns 'UNATTRIBUTED'; unreachable from the normalised backend.",
      "required_fix": "Return the em dash for any unknown source in formatMetric and add the assertion to check-provenance.mjs."
    },
    {
      "id": "DEV-R1-F05",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_integrity_provenance.py:548-609 and :629-668",
      "evidence": "No test asserts the no-previous-thesis message on a bootstrap-only palace, and the round-trip test reloads from Redis first so the JSONL half of the persistence scenario is not exercised for a new BOOTSTRAP drawer.",
      "required_fix": "Add the bootstrap-only prompt assertion and a JSONL-only reload assertion."
    }
  ],
  "closed": []
}
```
