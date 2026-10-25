# DEV Review — Round 2

## Summary

All three R1 findings are closed at `ab814e3`, with no regression, security, or critical finding introduced by the fix commit. The PR-built image now runs the Python suite green: `Ran 59 tests ... OK (skipped=9)`, and the nine skips name the repo-only paths the image does not package; the same modules run unskipped on a checkout (10/10). The single-source checker now prunes `SKIPPED_DIRS` via `os.walk`, and the new fixtures prove skipped-directory copies are ignored while a root duplicate still fails. The `rsi_tag` allocation is gone from the pre-gate path, and the `RSI=INACTIVE` rationale is pinned by exact equality. Core contract logic is unchanged and still correct. CI is green and the reviewed SHA equals the PR head; the change is approvable.

## Findings

### DEV-R1-F01 — [major] Python suite is not green in the image built by the PR
- Location: `backend/tests/test_contract_single_source.py:34-42`, `backend/tests/test_contract_no_codegen.py:49-61`
- Evidence: `docker build -f Dockerfile.backend -t robotrader-backend:contract-r2 .` → exit 0. `docker run --rm -e PYTHONPATH=. robotrader-backend:contract-r2 python -m unittest discover -s backend/tests -v` → `Ran 59 tests in 5.430s` / `OK (skipped=9)`, exit 0. The nine skips each name the missing path (`/app/scripts/check_contract_single_source.py`, `/app/engine-rs/Cargo.toml`) and are exactly the six checker-dependent cases plus three manifest cases; `test_python_baseline_resolves_the_named_key` still runs because `contracts/` is packaged. On a repository checkout the two modules run unskipped: `test_contract_single_source.py` `Ran 7 tests ... OK`, `test_contract_no_codegen.py` `Ran 3 tests ... OK`. CI's `python` job checks out the repo and runs the suite, and it passed. The PR body states image (`OK (skipped=9)`) and repo-checkout (`59 tests OK`) evidence separately.
- Required fix: (was) skip with a reason when repo-only paths are absent, or package them.
- Status: closed
- Origin: initial

### DEV-R1-F02 — [major] Single-source checker ignores its own skip list and false-fails outside the worktree
- Location: `scripts/check_contract_single_source.py:80-96`
- Evidence: `_iter_scanned_files` now uses `os.walk(root)` and prunes in place with `dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)` (`.git`, `target`, `node_modules`, `.worktrees`, `openspec`, `docs`, `.sdlc`); `grep` confirms `SKIPPED_DIRS` is consumed. New fixtures `test_skipped_directories_are_not_scanned` and `test_root_duplicate_is_reported_while_skipped_dirs_are_ignored` both pass; the latter reproduces the post-merge main-checkout layout (`contracts/` at root plus copies under `.worktrees/`, `docs/`, `openspec/`, `.sdlc/`) and asserts a root `duplicate.conf` still exits 1 while the skipped trees are absent from the report. `python3 scripts/check_contract_single_source.py --root .` → exit 0, sole declaration `contracts/policy_contract.conf`.
- Required fix: (was) prune `SKIPPED_DIRS` and add a fixture proving skipped copies are ignored while a root duplicate is reported.
- Status: closed
- Origin: initial

### DEV-R1-F03 — [minor] Per-tick `String` allocation added to `MomentumPod::on_market_event`
- Location: `engine-rs/crates/strategies/src/lib.rs:228-242`, `:273-287`
- Evidence: the pre-gate `rsi_tag` binding is removed; no `format!` remains between the gates and the two emit branches (`grep -n "format!"` shows only the intent rationales at lines 230-283 in `MomentumPod`). The rationale is now built by a three-case `match` inside each emit branch. `rsi_guard_is_reported_inactive_when_rsi_14_is_absent` asserts exact equality with `Momentum Long: OBI +0.50, z=2.00, catalyst=0.50 RSI=INACTIVE` (`momentum_rules.rs:143-144`). `cargo test --all-targets` → exit 0, 18 momentum tests pass.
- Required fix: (was) build the tag lazily inside the emit branches; keep `RSI=INACTIVE` observable.
- Status: closed
- Origin: initial

### New findings
None. The R2 diff touches only the three fix areas (five files: two Python test modules, the checker, the momentum pod, and its test); no regression, security, or critical defect was introduced.

## Core contract verification (unchanged by R2)

- Parity: `engine-rs/crates/common/src/lib.rs` `AssetOverride` exposes the eleven keys; eight optional fields use `#[serde(default)]` `Option<f64>`. Python `AssetOverride` (`backend/core/schemas.py:40-52`) exposes the same eleven. `test_contract_roundtrip.py` passes in both image and checkout.
- Strict decode: `deny_unknown_fields` on `PodAllocation`, `AssetOverride`, and `PolicyEnvelope`; `MarketEvent` and `OnChainTokenSafety` remain tolerant. Rust `asset_override_contract` (14 tests) passes.
- Optional RSI: `OrderbookTick.rsi_14: Option<f64>` with `#[serde(default)]`; `RSI=INACTIVE` when an override exists and the input is absent.
- Directional gates: OBI `>=` / `<= -`, RSI `<=` long / `>=` short with 70.0 / 30.0 defaults, support `>=`, resistance `<=`, invalidation strict `>` / `<`, TP/SL `bps / 100` (45.0 / 30.0 defaults); no override keeps pod OBI and ATR TP/SL.
- TTL single source: `SAFE_BASELINE_TTL_SECONDS=900` only in `contracts/policy_contract.conf`; Rust `include_str!` + const fn, Python import, checker enforces.
- No secrets in the diff; no hot-path LLM/blocking; `HardRiskGate` and `risk-gate` untouched.

## Checks run

- `cd engine-rs && cargo test --all-targets` → exit 0; 8 suites `ok`, 40 tests total (2+1+14+0+0+5+0+18), including `asset_override_contract` (14) and `momentum_rules` (18).
- `docker build -f Dockerfile.backend -t robotrader-backend:contract-r2 .` → exit 0.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:contract-r2 python -m unittest discover -s backend/tests -v` → exit 0; `Ran 59 tests in 5.430s` / `OK (skipped=9)`.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -p "test_contract_single_source.py" -v` (checkout) → exit 0; `Ran 7 tests ... OK`, 0 skips.
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -p "test_contract_no_codegen.py" -v` (checkout) → exit 0; `Ran 3 tests ... OK`, 0 skips.
- `python3 scripts/check_contract_single_source.py --root .` → exit 0; sole declaration `contracts/policy_contract.conf`, both `EXEMPT_DEFAULTS`.
- `openspec validate align-asset-override-contract --strict` → `Change 'align-asset-override-contract' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check align-asset-override-contract` → `check: PASS` (35 tasks done, 0 open).
- `gh pr checks 13` → rust pass, python pass, frontend pass, sdlc pass (exit 0).
- `gh pr view 13 --json isDraft,headRefOid,mergeable` → `headRefOid=ab814e31fa5f9252987d01b740cafbcea1bda598`, `isDraft=true`, `mergeable=MERGEABLE`.
- `git rev-parse HEAD` → `ab814e31fa5f9252987d01b740cafbcea1bda598` (equals PR head).

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "dev",
  "round": 2,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "ab814e31fa5f9252987d01b740cafbcea1bda598",
  "verdict": "APPROVE",
  "summary": "All three R1 findings are closed at ab814e3 with no regression; the image suite is green, the checker prunes its skip list, the hot-path allocation is gone, core contract logic is unchanged, and CI is green at the PR head.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "backend/tests/test_contract_single_source.py:34-42; backend/tests/test_contract_no_codegen.py:49-61",
      "evidence": "Image suite: Ran 59 tests, OK (skipped=9), exit 0; the 9 skips name the missing repo-only paths. Checkout modules run unskipped (7+3 tests OK). CI python job passed on a repo checkout; PR body separates image and repo evidence.",
      "required_fix": "N/A — fixed and verified."
    },
    {
      "id": "DEV-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "scripts/check_contract_single_source.py:80-96",
      "evidence": "_iter_scanned_files uses os.walk and prunes SKIPPED_DIRS in place; two new fixtures pass, including the post-merge layout where skipped-tree copies are ignored and a root duplicate still exits 1; --root . exits 0.",
      "required_fix": "N/A — fixed and verified."
    },
    {
      "id": "DEV-R1-F03",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "engine-rs/crates/strategies/src/lib.rs:228-242,273-287",
      "evidence": "Pre-gate rsi_tag removed; no format! before the emit branches; rationale built inside each emit branch, and the exact RSI=INACTIVE assertion passes.",
      "required_fix": "N/A — fixed and verified."
    }
  ],
  "closed": ["DEV-R1-F01", "DEV-R1-F02", "DEV-R1-F03"]
}
```
