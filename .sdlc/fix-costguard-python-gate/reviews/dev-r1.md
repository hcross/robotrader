# DEV Review — Round 1

## Summary

APPROVE at `ea4f3a9`. The CostGuard now fails closed without an injected measured-PnL source, runs kill switch → strictly positive PnL → `(0, $25.00]` bound → 10 % share → watermark (unless `force`) → rolling 24 h epoch cap on both paths, derives daily spend and epoch totals from exclusive `86_400_000` ms windows under an `RLock`, hydrates lazily from an injectable module-anchored ledger, and reports the truthful status and single backend watermark. I independently ran the Dockerized Python suite (172 tests, OK skipped=9), `cargo test --all-targets`, the frontend build/provenance checks, OpenSpec/SDLC checks, and a live `/status` plus forced-refill smoke against the built image; all matched the approved SPEC/PLAN. Two non-blocking minors remain: the dev edited PLAN artifacts after the plan-approved SHA, and hydration aborts on valid-JSON non-object ledger lines instead of skipping them.

## Findings

### DEV-R1-F01 — [minor] PLAN artifacts were edited after the plan-approved SHA

- Location: `openspec/changes/fix-costguard-python-gate/design.md:215`, `openspec/changes/fix-costguard-python-gate/tasks.md:46` (plus the `covers:` annotations on tasks 2.1/2.8)
- Evidence: `git diff ad721ce HEAD -- openspec/changes/fix-costguard-python-gate/design.md openspec/changes/fix-costguard-python-gate/tasks.md` shows non-checkbox edits introduced by `4f1c9c5`, while the PLAN verdict is bound to `ad721ce` (`.sdlc/fix-costguard-python-gate/reviews/plan-r2.md`). `sdlc/PROTOCOL.md` §4 limits `sdlc-dev` to code, tests, `tasks.md` checkboxes and `revisions/*`, and §14 requires the PLAN `APPROVE` at the current SHA. The edits implement the plan reviewer's own F16/F17 required fixes and change no design decision or behaviour.
- Required fix: Either run a PLAN R3 over the updated `design.md`/`tasks.md` and record the new `reviewed_sha`, or record an explicit conductor/plan-owner acceptance of the post-approval F16/F17 documentation edit in the issue and state that the plan SHA binding is intentionally superseded; otherwise restore the `ad721ce` text and leave F16/F17 as open non-blocking minors. No code change.
- Status: open
- Origin: initial

### DEV-R1-F02 — [minor] Hydration aborts on valid-JSON non-object or non-numeric ledger lines instead of skipping them

- Location: `backend/agents/monitor.py:244-264`
- Evidence: injected a temporary ledger whose newest line was `null`; `hydrate_from_ledger()` raised `AttributeError: 'NoneType' object has no attribute 'get'`. A `[1, 2]` line raised the same `AttributeError`; a non-numeric `cost_usd`/token field raises `ValueError`. Only `UnicodeDecodeError`/`JSONDecodeError` are caught. Design D11 and task 4.6 require malformed lines to be skipped, and an uncaught failure here also surfaces as a `/status` 5xx through lazy hydration. The ledger is append-only and app-written, so the exposure is corruption-only.
- Required fix: After `json.loads`, `continue` unless `isinstance(entry, dict)`, and wrap the `timestamp_ms`/token/`cost_usd` conversions in `try/except (TypeError, ValueError): continue`. Add a unit test with a `null` line ahead of an in-window object and one with a non-numeric `cost_usd`.
- Status: open
- Origin: initial

## Checks run

- `docker build -f Dockerfile.backend -t robotrader-backend:costguard-review .` → exit 0.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:costguard-review python -m unittest discover -s backend/tests -v` → `Ran 172 tests in 7.685s`, `OK (skipped=9)`, exit 0.
- `cd engine-rs && cargo test --all-targets` → all suites pass: 2 + 1 + 14 + 0 + 0 + 5 + 0 + 18 tests, `0 failed`, exit 0.
- `cd frontend && npm run build` → success, `dist/` written (`✓ built in 463ms`), exit 0.
- `node frontend/scripts/check-provenance.mjs` → `provenance wiring OK`, exit 0.
- `cd frontend && npm run lint` → exit 1 with exactly the five pre-existing errors on untouched lines: `App.jsx:113` (react-hooks/set-state-in-effect), `Dashboard.jsx:38` (`Icon` unused), `MasterOverview.jsx:65,66` (`checkoutHistory`, `bridgeHistory` unused), `MasterOverview.jsx:79` (`setCheckoutAddress` unused). The diff touches only `MasterOverview.jsx:401`.
- `openspec validate fix-costguard-python-gate --strict` → `Change 'fix-costguard-python-gate' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check fix-costguard-python-gate` → `check: PASS`; `spec-lint` PASS (Review Card 172 words, 1 diagram, ~1.4 min; 53 done, 0 open); `verdict-lint` PASS, exit 0.
- `gh pr checks 18` → `frontend`, `helm`, `python`, `rust`, `sdlc` all `pass`, exit 0.
- `gh pr view 18 --json isDraft,headRefOid,mergeable` → `isDraft: true`, `headRefOid: ea4f3a9760ecc15cdef8143a73d5ebcec01a9517`, `mergeable: MERGEABLE`.
- Live smoke against the built image (standalone, isolated empty ledger, port 8010): `/api/v1/status` → `contract_version 3`, `ENABLED_PROFIT_GATED`, `PROFIT_GATED_CAPPED_BY_ORCHESTRATOR`, watermark `2.0`, `measured_pnl_source_available true`, `epoch_refilled_usd 0`, `last_refill_rejection null`, `total_spent_usd 0`; `POST /api/v1/openrouter/refill {"force": true}` → `{"status":"rejected_no_realized_profit","reason":"Realized trading PnL ($0.00) <= 0; principal treasury protected","openrouter_balance_usd":8.5}`. `docker compose ps` was empty, so the compose-specific path was not re-run; the image smoke exercises the same endpoint contract.
- Grep gates all empty: `max(125.0`, `DISABLED_BY_SECURITY_POLICY` in `backend`, `state_store`/`REDIS_URL`/`read_text`/`splitlines` in `monitor.py`, `total_cost_usd =`, `epoch_refilled_usd =`, `?? 5.0`, stale ADR-0003 watermark. No Rust, dependency, schema, or secret change.
- Test isolation: every `OrchestratorAgent` construction in the suite passes an isolated `ledger_path` or, for the two `backend.server` subprocesses, `COSTGUARD_LEDGER_PATH`.
- Scope: this review wrote only `.sdlc/fix-costguard-python-gate/reviews/dev-r1.md`; no code, test, spec, design, task, or issue edit.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-costguard-python-gate",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "ea4f3a9760ecc15cdef8143a73d5ebcec01a9517",
  "verdict": "APPROVE",
  "summary": "The CostGuard fails closed without an injected measured source and applies the full kill-switch, positive-PnL, bound, profit-share, watermark, and rolling epoch gate on both paths with exclusive 86,400,000 ms windows, lazy isolated hydration, and truthful status/watermark; all required checks pass at the PR head, with two non-blocking minors recorded.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-costguard-python-gate/design.md:215; openspec/changes/fix-costguard-python-gate/tasks.md:46",
      "evidence": "git diff ad721ce HEAD shows non-checkbox edits to design.md and tasks.md introduced by 4f1c9c5, while the PLAN verdict is bound to ad721ce; sdlc/PROTOCOL.md section 4 forbids sdlc-dev from changing design, and section 14 requires the PLAN APPROVE at the current SHA. The edits are the plan reviewer's own F16/F17 documentation fixes and change no decision or behaviour.",
      "required_fix": "Run a PLAN R3 over the updated design.md/tasks.md and record the new reviewed_sha, or record explicit conductor/plan-owner acceptance of the post-approval F16/F17 edit; otherwise restore the ad721ce text and leave F16/F17 as open minors. No code change."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "backend/agents/monitor.py:244-264",
      "evidence": "A ledger whose newest line is null raises AttributeError in hydrate_from_ledger; a [1, 2] line raises the same, and a non-numeric cost_usd raises ValueError. Only UnicodeDecodeError and JSONDecodeError are caught, so malformed valid-JSON lines are not skipped as design D11 and task 4.6 require; lazy hydration also turns this into a /status 5xx.",
      "required_fix": "After json.loads, continue unless isinstance(entry, dict); wrap the timestamp/token/cost conversions in try/except (TypeError, ValueError) and continue; add tests with a null line and a non-numeric cost_usd ahead of an in-window object."
    }
  ],
  "closed": []
}
```
