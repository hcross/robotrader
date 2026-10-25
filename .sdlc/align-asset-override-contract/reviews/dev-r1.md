# DEV Review — Round 1

## Summary

The contract repair itself is sound: Rust/Python `AssetOverride` parity holds at eleven keys, strict decoding is scoped to the three policy types, the momentum gates match the approved scenarios, the TTL is single-sourced, and the CLI fails loud. CI is green and the reviewed SHA equals the PR head. Two majors block approval. First, the image built by the PR cannot run the Python suite green: five repo-path-dependent tests fail when `/app` is not shadowed by a host mount, contradicting the PR's "57 tests OK" evidence. Second, the single-source checker defines but never applies its `SKIPPED_DIRS`, so it false-fails on `.worktrees/`, `docs/`, and `openspec/`, contrary to approved task 1.2. One minor hot-path allocation is a follow-up.

## Findings

### DEV-R1-F01 — [major] Python suite is not green in the image built by the PR
- Location: `backend/tests/test_contract_single_source.py:17`, `backend/tests/test_contract_no_codegen.py:24-25`, `Dockerfile.backend:12-34`
- Evidence: `docker build -f Dockerfile.backend -t robotrader-backend:contract-review .` → exit 0. Then `docker run --rm -e PYTHONPATH=. robotrader-backend:contract-review python -m unittest discover -s backend/tests -v` → `Ran 57 tests ... FAILED (failures=1, errors=4)`. Errors: four `test_contract_single_source` cases with `FileNotFoundError: '/app/scripts/check_contract_single_source.py'`; one `test_no_schema_codegen_dependency_in_manifests` failure with `missing manifest: /app/engine-rs/Cargo.toml`. The runtime image copies only `contracts/`, `backend/`, and the binary (`Dockerfile.backend:27,31,34`), so `scripts/` and the Cargo manifests are absent. The PR body claims "`PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` | **57 tests OK**", which is not reproducible against the image alone; the author's evidence must have supplied repo files the image does not contain.
- Required fix: make the new tests hermetic — `skipTest` (or an existence guard) when `scripts/check_contract_single_source.py` and `engine-rs/Cargo.toml` are absent, so they still run in CI/host checkouts but do not fail in the runtime image — or package the required dev paths. Verifiable: rebuild the image and rerun the exact `docker run` command above with zero failures/errors, then confirm the tests still run and pass from the repository checkout.
- Status: open
- Origin: initial

### DEV-R1-F02 — [major] Single-source checker ignores its own skip list and false-fails outside the worktree
- Location: `scripts/check_contract_single_source.py:42` (`SKIPPED_DIRS`), `scripts/check_contract_single_source.py:79-87` (`_iter_scanned_files`)
- Evidence: `grep -n SKIPPED_DIRS scripts/check_contract_single_source.py` returns only the definition at line 42; `_iter_scanned_files` walks `root.rglob("*")` at line 81 and never prunes skipped directories. A temporary root containing the contract plus duplicates under `.worktrees/other-change/contracts/policy_contract.conf`, `docs/example.py`, and `openspec/changes/x/example.yaml` produced `exit=1` and named all three, whereas approved task 1.2 requires skipping `.git/`, `target/`, `node_modules/`, `.worktrees/`, `openspec/`, `docs/`, and `.sdlc/`. In this repository's one-worktree-per-change workflow, running the documented `--root .` from the main checkout will find every sibling worktree's `contracts/policy_contract.conf` and fail spuriously.
- Required fix: prune `SKIPPED_DIRS` in `_iter_scanned_files` (and skip the checker's own tree as intended), then extend `backend/tests/test_contract_single_source.py` with a fixture asserting a duplicate under `.worktrees/`, `docs/`, or `openspec/` is ignored while a duplicate at the root is still reported. Verifiable: the new fixture passes and the real-root check still exits 0.
- Status: open
- Origin: initial

### DEV-R1-F03 — [minor] Per-tick `String` allocation added to `MomentumPod::on_market_event`
- Location: `engine-rs/crates/strategies/src/lib.rs:167-171`
- Evidence: `rsi_tag` is built before the entry gates: `" RSI=INACTIVE".to_string()` and `format!(" RSI={:.1}", rsi)` allocate on every `OrderbookTick` for override-bearing symbols (and when `rsi_14` is present), even when no intent is emitted. The pre-existing code allocated only inside the emit branches. Checklist §6 forbids new per-tick allocation/`format!` in the hot path.
- Required fix (follow-up, non-blocking): compute the tag lazily inside the two emit branches, or keep a static `&str` for the inactive case and format only when an intent is actually produced. A rationale-equality test should keep `RSI=INACTIVE` observable.
- Status: open
- Origin: initial

## Checklist walk

- Scope: only approved spec/plan files plus SDLC ledger artifacts; no dependency bump or codegen. PASS.
- Correctness: eleven-key parity, optionality, strict decode scope, directional OBI, RSI/S-R/invalidation/TP-SL semantics all match the spec and are covered by tests. PASS.
- Hot path: no LLM or blocking I/O; `HardRiskGate` untouched. One new per-tick allocation (F03). PASS with minor.
- Contracts: Rust/Python agreement proven by the round-trip test; TTL single-sourced at runtime. PASS.
- Security: no secrets, keys, or production addresses. PASS.
- Tests: Rust suites green; host Python suite green except the pre-existing `test_health` host dependency; image suite not green (F01). FAIL.
- Docker/CI: builder copies `contracts/` and `Cargo.lock`, builds `--locked`; runtime copies `contracts/`; CI prebuilds the node binary and runs the check. PASS, except the image-suite gap (F01).
- Operations: fail-loud CLI, documented rollback and migration in the PR body. PASS.

## Checks run

- `cd engine-rs && cargo test --all-targets` → exit 0; all 8 suites `ok` (40 tests), including `asset_override_contract` (14), `momentum_rules` (18), and `test_full_multi_pod_backtest_and_rug_rejection`.
- `cd engine-rs && cargo build --bin robotrader-node` → exit 0; `engine-rs/target/debug/robotrader-node` exists.
- `docker build -f Dockerfile.backend -t robotrader-backend:contract-review .` → exit 0.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:contract-review python -m unittest discover -s backend/tests -v` → **FAILED (failures=1, errors=4), Ran 57 tests** (F01).
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` (host) → Ran 49 tests; 1 error: `test_health` `ModuleNotFoundError: fastapi` (host interpreter only; pre-existing/environmental).
- `python3 scripts/check_contract_single_source.py --root .` → exit 0, prints sole declaration and both `EXEMPT_DEFAULTS`.
- Duplicate-negative temp root with `.worktrees/`, `docs/`, `openspec/` copies → exit 1 naming all three (F02; should skip).
- `openspec validate align-asset-override-contract --strict` → `Change 'align-asset-override-contract' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check align-asset-override-contract` → `check: PASS` (35 tasks done, 0 open).
- `gh pr checks 13` → frontend pass, python pass, rust pass, sdlc pass.
- `gh pr view 13 --json isDraft,headRefOid,mergeable` → `headRefOid=c0e8435513fc0ba8e817ba8297fbfa4af9eb241c`, `isDraft=true`, `mergeable=MERGEABLE`.
- CLI: unknown top-level key → exit 2, stdout empty, stderr names `unexpected`; unknown override key → exit 2, names `trailing_stop_bps`; missing required key → exit 2, names `catalyst_score`; valid supplied envelope → exit 0, `total_trades=0`, `rejected_orders=7`; `--contract-roundtrip` → exit 0, six top-level keys and exactly eleven override keys.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "c0e8435513fc0ba8e817ba8297fbfa4af9eb241c",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Contract parity and rule semantics are correct, but the PR-built image cannot run the Python suite green and the single-source checker ignores its approved skip list.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_contract_single_source.py:17; backend/tests/test_contract_no_codegen.py:24; Dockerfile.backend:12-34",
      "evidence": "Image-only run: Ran 57 tests, FAILED (failures=1, errors=4); /app/scripts/check_contract_single_source.py and /app/engine-rs/Cargo.toml are missing, contradicting the PR's 57-tests-OK claim.",
      "required_fix": "Make the new tests skip when repo-only paths are absent (or package them), then rebuild and rerun the image suite with zero failures/errors while keeping them green in CI."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "scripts/check_contract_single_source.py:42,79-87",
      "evidence": "SKIPPED_DIRS is never referenced; a temp root with duplicates in .worktrees/, docs/, and openspec/ exits 1, whereas approved task 1.2 requires skipping those directories.",
      "required_fix": "Prune SKIPPED_DIRS in _iter_scanned_files and add a fixture proving a duplicate under those directories is ignored while a root duplicate is still reported."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/strategies/src/lib.rs:167-171",
      "evidence": "rsi_tag allocates a String before the entry gates on every OrderbookTick for override-bearing symbols, even when no intent is emitted.",
      "required_fix": "Build the rationale tag lazily inside the emit branches or use a static marker for the inactive case; keep RSI=INACTIVE observable."
    }
  ],
  "closed": []
}
```
