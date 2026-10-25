# DEV Review — Round 2

## Summary

Closure review at `7e5fd0512aab91925fbd9e16a128380a4618a20c` (PR #14 head). DEV-R1-F01 is **closed**: `test_contract_roundtrip.py` and `test_policy_ingestion.py` now build their commands through `resolve_robotrader_binary(ENGINE_DIR)`, and `grep` finds no `DEBUG_BINARY`, `cargo run`, or `"cargo"` fallback in either module. The correction diff touches only those two modules plus the SDLC ledger, so no other surface could regress. I rebuilt `robotrader-backend:infra-r2` and ran the suite as shipped: `Ran 66 tests`, `OK (skipped=9)`, exit 0, zero errors. Helm lint/render/invalid-budget cases, Rust tests, the resolver and 503 contract tests, package markers, dependency removal, and CI wiring all still pass; all five PR checks are green at the reviewed SHA. No new finding qualifies under the round-2 closure rules.

## Findings

### DEV-R1-F01 — [major] Image suite does not pass as shipped: two test modules ignore the shared resolver and fall back to `cargo`

- Location: `backend/tests/test_contract_roundtrip.py:15,35-36`; `backend/tests/test_policy_ingestion.py:13,22-27`
- Evidence: `grep -n "DEBUG_BINARY\|cargo run\|\"cargo\"\|'cargo'" backend/tests/test_contract_roundtrip.py backend/tests/test_policy_ingestion.py` → no match. Both modules import `resolve_robotrader_binary` from `backend.core.state_store` and return `[str(resolve_robotrader_binary(ENGINE_DIR)), ...]`. `resolve_robotrader_binary` (`backend/core/state_store.py:55-69`) is debug-first, release-fallback, and raises `RustBinaryNotFoundError` without spawning a compiler. Image layout: `/app/engine-rs/target/release/robotrader-node` executable; `target/debug/...` absent; `command -v cargo` → `NO_CARGO`. As-shipped suite: `docker run --rm -e PYTHONPATH=. robotrader-backend:infra-r2 python -m unittest discover -s backend/tests -v` → `Ran 66 tests in 5.506s`, `OK (skipped=9)`, exit 0, zero `ERROR`/`FAIL` lines.
- Required fix: none outstanding.
- Status: closed
- Origin: initial

## Follow-ups (non-blocking)

- Plan-r2 recorded that `design.md:157` (R4) says an explicit zero fails; the current helper does fail on `--set env.maxDailyLlmBudgetUsd=0` (verified exit 1), so the wording is accurate as shipped. No action required here; noted only to close the plan-r2 remark.
- `strands-agents` remains declared with the documented follow-up in issue #9 (wire it into the warm path or remove it with the docs/ADR claims). Out of scope for this change.

## Checks run

- `docker build -f Dockerfile.backend -t robotrader-backend:infra-r2 .` → exit 0; image `sha256:e2a44e7eaa73...`.
- Image layout → release binary present/executable (`-rwxr-xr-x`, 922768 B); `target/debug/robotrader-node` absent; `NO_CARGO`.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:infra-r2 python -m unittest discover -s backend/tests -v` → exit 0; `Ran 66 tests in 5.506s`, `OK (skipped=9)`; zero errors/failures.
- `cd engine-rs && cargo test --all-targets` → exit 0; 8 test binaries, 40 tests total, 0 failed.
- `helm lint charts/robotrader` → exit 0; `1 chart(s) linted, 0 chart(s) failed` (only the icon INFO).
- `helm template charts/robotrader` → exit 0; 1 Service, 1 Deployment, 0 Ingress; `OPENROUTER_API_KEY`, `SOLANA_RPC_URL`, `REDIS_URL`, `MAX_DAILY_LLM_BUDGET_USD` present.
- Empty budget `--set env.maxDailyLlmBudgetUsd=""` → exit 0, renders `"5.0"`.
- Invalid budgets `-1`, `0`, `--set-string abc` → each exit 1 with `env.maxDailyLlmBudgetUsd must be a positive number`.
- Ingress override (`ingress.enabled=true`, host `robotrader.example.test`, path `/`) → exit 0; one Ingress with the configured host/path.
- Service selector equals Deployment pod labels; custom `redisUrl` / `7.5` render correctly.
- `grep -rn "cargo" backend/ --include="*.py"` → only two advisory error-message strings (`errors.py:14`, `test_missing_binary.py:150`), no executable fallback.
- `grep -rn "DEBUG_BINARY" backend/ engine-rs/` → no match.
- Package markers `backend/__init__.py` and `backend/tests/__init__.py` present.
- `backend/tests/test_missing_binary.py` → resolver debug-first/release-fallback/no-compiler tests plus the six-endpoint uniform 503 child test, all passing in the image.
- Dependencies: no `litellm` in `backend/pyproject.toml`; no `name = "litellm"` block in `backend/poetry.lock`; `backend/config.py` absent.
- `openspec validate harden-build-packaging --strict` → `Change 'harden-build-packaging' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → `check: PASS`, exit 0 (24 tasks done, 0 open).
- `git diff --quiet master...HEAD -- .github/workflows/sdlc-checks.yml` → exit 0 (unchanged); CI has a `helm` job with `charts/**` path filters; all PR checks green.
- `gh pr checks 14` → frontend pass, helm pass, python pass, rust pass, sdlc pass.
- `gh pr view 14 --json isDraft,headRefOid,mergeable` → head `7e5fd0512aab91925fbd9e16a128380a4618a20c`, `isDraft: true`, `mergeable: MERGEABLE`.
- Secret scan of the correction diff → no match.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "dev",
  "round": 2,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "7e5fd0512aab91925fbd9e16a128380a4618a20c",
  "verdict": "APPROVE",
  "summary": "DEV-R1-F01 is closed: both test modules use the shared resolver, the release-only image suite passes as shipped (66 tests, OK, skipped=9), and all required checks are green at the PR head.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "backend/tests/test_contract_roundtrip.py:15,35-36; backend/tests/test_policy_ingestion.py:13,22-27",
      "evidence": "Both modules call resolve_robotrader_binary(ENGINE_DIR); no DEBUG_BINARY/cargo fallback remains. docker run --rm -e PYTHONPATH=. robotrader-backend:infra-r2 python -m unittest discover -s backend/tests -v -> Ran 66 tests, OK (skipped=9), exit 0, zero errors; image has only target/release and no cargo.",
      "required_fix": "None outstanding."
    }
  ],
  "closed": ["DEV-R1-F01"]
}
```
