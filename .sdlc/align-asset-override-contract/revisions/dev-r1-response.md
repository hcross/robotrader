stage: dev
round: 1
head_sha: 2815e5097e1fe283b74a13bfc03880453fef46f2
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: >-
      Added `_require_repo_checkout()` skips to the six checker-dependent cases in
      `backend/tests/test_contract_single_source.py` and a `setUp` skip guard to
      `backend/tests/test_contract_no_codegen.py`; the skip message names the
      missing repository paths. The TTL resolution test still runs in the image
      because `contracts/` is packaged. Rebuilt
      `docker build -f Dockerfile.backend -t robotrader-backend:contract-review .`
      (exit 0) and ran the exact reviewer command
      `docker run --rm -e PYTHONPATH=. robotrader-backend:contract-review python -m unittest discover -s backend/tests -v`
      -> `Ran 59 tests ... OK (skipped=9)`, exit 0, zero failures/errors. The
      repository-checkout run (container copy with the Linux node binary) ->
      `Ran 59 tests ... OK`, zero skips; the two affected modules run 10/10 on the
      host checkout. The PR body now distinguishes image (`OK (skipped=9)`) from
      repo-checkout (`59 tests OK`) and no longer claims a single 57-test result.
  - id: DEV-R1-F02
    action: fixed
    evidence: >-
      `_iter_scanned_files` in `scripts/check_contract_single_source.py` now walks
      with `os.walk` and prunes `dirnames[:]` against `SKIPPED_DIRS` (`.git`,
      `target`, `node_modules`, `.worktrees`, `openspec`, `docs`, `.sdlc`).
      Added `test_skipped_directories_are_not_scanned` and
      `test_root_duplicate_is_reported_while_skipped_dirs_are_ignored` in
      `backend/tests/test_contract_single_source.py`. A simulated post-merge main
      checkout (contract at root plus duplicates under
      `.worktrees/other/contracts/policy_contract.conf`, `docs/example.py`, and
      `openspec/changes/x/example.yaml`) now exits 0; the same root plus a
      root-level `duplicate.conf` exits 1 and names only `duplicate.conf`. The
      literal `--root .` from the current main checkout cannot be exercised
      before merge because `master` does not yet contain `contracts/`; the fixture
      reproduces that post-merge layout. `--root .` from the worktree exits 0.
  - id: DEV-R1-F03
    action: fixed
    evidence: >-
      Removed the pre-gate `rsi_tag` allocation from
      `engine-rs/crates/strategies/src/lib.rs`; the rationale is now built by a
      three-case `match` inside each emit branch, so no `String` is allocated for
      an OrderbookTick that produces no intent. The inactive marker remains
      observable, and `rsi_guard_is_reported_inactive_when_rsi_14_is_absent` now
      asserts exact rationale equality:
      `Momentum Long: OBI +0.50, z=2.00, catalyst=0.50 RSI=INACTIVE`.
      `cd engine-rs && cargo test --all-targets` -> exit 0, 40 tests (14 contract,
      18 momentum).
