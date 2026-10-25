stage: dev
round: 1
head_sha: 71711ccebe7b602a1b8ac78cf5b2c3a41a948008
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: >-
      Both modules now build their commands through the shared resolver:
      `backend/tests/test_contract_roundtrip.py` imports
      `resolve_robotrader_binary` from `backend.core.state_store` and
      `_roundtrip_command()` returns
      `[str(resolve_robotrader_binary(ENGINE_DIR)), "--contract-roundtrip"]`;
      `backend/tests/test_policy_ingestion.py` does the same in
      `_policy_command()`. The `DEBUG_BINARY` constants and both `cargo run`
      fallbacks are deleted (`grep` for `DEBUG_BINARY`/`"cargo"`/`cargo run` in
      the two modules returns no match). Rebuilt
      `docker build -f Dockerfile.backend -t robotrader-backend:infra .` (exit 0,
      image `e2a44e7eaa73`); the as-shipped layout has the executable release
      binary, no `target/debug`, and no `cargo` on `PATH`. Re-ran the reviewer's
      exact command
      `docker run --rm -e PYTHONPATH=. robotrader-backend:infra python -m unittest discover -s backend/tests -v`
      with no debug copy -> `Ran 66 tests in 5.405s`, `OK (skipped=9)`, exit 0,
      zero errors/failures. The 9 skips are the repo-only skips. Also re-ran
      `cd engine-rs && cargo test --all-targets` (exit 0, 40 tests),
      `openspec validate harden-build-packaging --strict` (valid), and
      `scripts/sdlc/sdlc.sh check harden-build-packaging` (PASS). The PR body now
      states the as-is image evidence and no longer mentions an ephemeral
      debug-path copy.
