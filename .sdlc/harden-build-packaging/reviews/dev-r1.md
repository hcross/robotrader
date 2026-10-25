# DEV Review — Round 1

## Summary

The change is sound and matches the approved spec/plan: Helm lints and renders, budget validation fails closed, the image is release-only from the committed lockfile, the shared debug-first resolver has no compiler fallback, the uniform 503 contract holds for every endpoint, and all CI jobs are green at the reviewed SHA. One major defect remains. The runtime image ships only `target/release`, but `test_contract_roundtrip.py` and `test_policy_ingestion.py` still hard-code `target/debug` and fall back to `cargo`. Run as shipped, the image suite fails with 6 errors (`FileNotFoundError: 'cargo'`); the DEV evidence's "Ran 66 tests ... OK" was obtained only with an ephemeral debug-path copy that the shipped image does not contain. Both modules must use the shared resolver.

## Findings

### DEV-R1-F01 — [major] Image suite does not pass as shipped: two test modules ignore the shared resolver and fall back to `cargo`

- Location: `backend/tests/test_contract_roundtrip.py:18,35-46` and `backend/tests/test_policy_ingestion.py:15,21-34`
- Evidence: The image ships `/app/engine-rs/target/release/robotrader-node` (executable) and has no `target/debug` and no `cargo` (verified: `ls -la /app/engine-rs/target/release/robotrader-node` OK; `ls /app/engine-rs/target/debug/...` "No such file"; `which cargo` "no cargo"). Running the suite as-is:
  `docker run --rm -e PYTHONPATH=. robotrader-backend:infra-review python -m unittest discover -s backend/tests -v`
  → `Ran 66 tests in 6.454s` / `FAILED (errors=6, skipped=9)` (51 ok). All six errors are in the two modules and end in `FileNotFoundError: [Errno 2] No such file or directory: 'cargo'`, because `DEBUG_BINARY` is absent and the local `cargo run` fallback is selected. `test_missing_binary` and the resolver/503 contract pass in the image. This contradicts the DEV evidence in issue #9 (`DEV-R1 evidence — ... The Python suite in the image: Ran 66 tests ... OK (skipped=9)`), which relied on an ephemeral debug-path copy not present in the shipped image. It also leaves exactly the divergent lookup + compiler fallback the change removed from `state_store.py`.
- Required fix: Build both modules' commands through `backend.core.state_store.resolve_robotrader_binary(ENGINE_DIR)` (debug-first, release fallback) and delete the `cargo run` branches in `_roundtrip_command` and `_policy_command`. Re-run `docker run --rm -e PYTHONPATH=. robotrader-backend:infra-review python -m unittest discover -s backend/tests -v` and require `OK` with zero errors.
- Status: open
- Origin: initial

## Checks run

- `helm lint charts/robotrader` → exit 0; `1 chart(s) linted, 0 chart(s) failed` (only `[INFO] Chart.yaml: icon is recommended`, no `[ERROR]`).
- `helm template charts/robotrader` → exit 0; 1 `kind: Deployment`, 1 `kind: Service`, 0 `kind: Ingress`; `MAX_DAILY_LLM_BUDGET_USD: "5.0"`, `REDIS_URL: ""`, `OPENROUTER_API_KEY` and `SOLANA_RPC_URL` preserved.
- Empty budget: `helm template ... --set env.maxDailyLlmBudgetUsd=""` → exit 0, `"5.0"`. Invalid budgets: `-1`, `0`, `--set-string abc` → each exit 1 with `env.maxDailyLlmBudgetUsd must be a positive number` (no `%!f(...)` marker).
- Ingress override: `--set ingress.enabled=true --set ingress.host=robotrader.example.test --set ingress.path=/` → exit 0, one Ingress with the configured host/path.
- `helm template ... --set env.redisUrl=redis://cache:6379/0 --set env.maxDailyLlmBudgetUsd=7.5` → `REDIS_URL: "redis://cache:6379/0"`, `MAX_DAILY_LLM_BUDGET_USD: "7.5"`.
- Service vs pod labels: `--show-only templates/service.yaml` selector `app.kubernetes.io/name: robotrader` + `app.kubernetes.io/instance: release-name` equals the Deployment pod labels; Service `port: 80`, `targetPort: 8000`.
- `helm show values charts/robotrader` → documents `redisUrl: ""`, `maxDailyLlmBudgetUsd: 5.0`, with a comment line per key.
- `cd engine-rs && cargo test --all-targets` → exit 0; 8 test binaries, 40 tests total, 0 failed.
- `docker build -f Dockerfile.backend -t robotrader-backend:infra-review .` → exit 0 (builder copies `Cargo.lock` before `crates/` and runs `cargo build --release --locked`; `.dockerignore` does not exclude the lock).
- Image layout: release binary present and executable at `/app/engine-rs/target/release/robotrader-node`; `/app/engine-rs/target/debug/robotrader-node` absent; no `cargo` on `PATH`.
- `docker run --rm -e PYTHONPATH=. robotrader-backend:infra-review python -m unittest discover -s backend/tests -v` (as-is, no debug copy) → `Ran 66 tests in 6.454s`, `FAILED (errors=6, skipped=9)`; 6 errors in `test_contract_roundtrip` (4) and `test_policy_ingestion` (2); `test_missing_binary` all pass.
- Documented local procedure: `cargo build --manifest-path engine-rs/Cargo.toml --bin robotrader-node` → exit 0; `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` → discovery works (no `Start directory is not importable`), 52 tests ran; the 2 errors are host-environment only (`ModuleNotFoundError: fastapi` on the reviewer machine). The CI `python` job using the same procedure is green.
- `openspec validate harden-build-packaging --strict` → `Change 'harden-build-packaging' is valid`, exit 0.
- `scripts/sdlc/sdlc.sh check harden-build-packaging` → `check: PASS`, exit 0 (24 tasks done, 0 open).
- `gh pr checks 14` → `frontend` pass, `helm` pass, `python` pass, `rust` pass, `sdlc` pass.
- `gh pr view 14 --json headRefOid,statusCheckRollup` → head `0e2074758b12402bdfb5ba68d9e4a6e6d0e205e5`, all five checks `SUCCESS`; `isDraft: true`, `mergeable: MERGEABLE`.
- `git diff --quiet master...HEAD -- .github/workflows/sdlc-checks.yml` → exit 0 (unchanged).
- Dependencies: no `litellm` in `backend/pyproject.toml`, no `name = "litellm"` block in `poetry.lock` (2 residual string occurrences are `strands-agents` extras metadata, documented in design R8), `backend/config.py` absent, no `import litellm` / `backend.config`; `poetry -C backend check --lock` → `All set!`; `strands-agents` retained and the follow-up is recorded in the issue and PR body.
- Secrets scan of the diff (key/token/private-key patterns) → no match.
- Scope: 19 non-ledger changed files, matching the approved spec/plan (plus `backend/agents/trading.py`, named in the design footprint note). `/ws/chat` left outside the HTTP 503 contract; `/api/v1/health` independent of the binary.

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "harden-build-packaging",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "0e2074758b12402bdfb5ba68d9e4a6e6d0e205e5",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The change meets the spec and CI is green, but the release-only image suite fails as shipped: two test modules hard-code target/debug and fall back to cargo instead of the shared resolver.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/tests/test_contract_roundtrip.py:18,35-46; backend/tests/test_policy_ingestion.py:15,21-34",
      "evidence": "docker run --rm -e PYTHONPATH=. robotrader-backend:infra-review python -m unittest discover -s backend/tests -v -> Ran 66 tests, FAILED (errors=6, skipped=9); each error is FileNotFoundError: 'cargo' because the image has only target/release and no cargo. The DEV evidence's 66-test OK relied on an ephemeral debug-path copy absent from the shipped image.",
      "required_fix": "Build both test modules' commands with backend.core.state_store.resolve_robotrader_binary and remove the cargo run fallbacks, then re-run the image suite as-is and require OK with zero errors."
    }
  ],
  "closed": []
}
```
