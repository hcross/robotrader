# DEV Review — Round 1

## Summary

Lane M wiring mirrors prior leaf warm-path implementations and adds XRP-specific
catalyst, support/resistance, and take-profit calibration. Rust and Python tests
pass (298), CI is green, and the reviewed SHA matches PR head. One material
correctness defect remains: `rust_pods` is a list of dictionaries, but
`pod_allocations` computes `enabled = p_name in rust_pods_list` with string
names, so every XRP pod is marked disabled with zero weight. This contradicts
the `pod_allocations` deliverable and leaves `weight_per_pod` unused. Fix the
membership normalization before approval.

## Findings

### DEV-R1-F01 — [major] PolicyEnvelope marks all XRP pods disabled
- Location: `backend/agents/orchestrator.py:320-329`
- Evidence: `leaf_state["rust_pods"]` contains dicts such as
  `{"slot_id": "pod_carry", "pod_code": "xrp_rlusd_mm_carry", ...}`, but the
  membership test compares strings. A direct call of
  `run_leaf_agent_reflection("leaf-xrp", ...)` returns
  `pod_carry=pod_momentum=pod_onchain_alpha=pod_sniper` with
  `enabled=False`, `capital_weight=0.0`, while slot ids are
  `pod_carry`, `pod_momentum`, `pod_onchain_alpha`.
- Required fix: derive
  `pod_slot_ids = {p.get("slot_id") if isinstance(p, dict) else p for p in rust_pods_list}`
  before the loop, use `enabled = p_name in pod_slot_ids`, and
  `weight_per_pod = round(1.0 / max(1, len(pod_slot_ids)), 2)`, retaining
  fallback string support. Add an assertion in the XRP test that all three XRP
  slots are enabled with non-zero weight.
- Status: open
- Origin: initial

## Checks run
- `cargo test --manifest-path engine-rs/Cargo.toml` → PASS (all crates, no failures)
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests -v` → 298 tests OK
- `cd frontend && npm run build` → not run locally (vite not installed in this
  worktree; `npm run build` exits with `sh: vite: command not found`);
  `gh pr checks 206` → frontend PASS
- `docker compose up --build -d` → not run locally (`worktree/.env` missing);
  `gh pr checks 206` → python PASS
- `gh pr checks 206` → frontend, helm, python, rust all PASS

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-xrp-warm-path",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "f375f53937cd64a23ac35572bebba40cba28b82b",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Warm-path wiring is consistent and checks pass, but compiled PolicyEnvelope disables every XRP pod because membership compares strings to dicts.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/agents/orchestrator.py:320-329",
      "evidence": "Direct reflection returns pod_carry=pod_momentum=pod_onchain_alpha=pod_sniper enabled=False/capital_weight=0.0 despite rust_pods slot_ids pod_carry, pod_momentum, pod_onchain_alpha.",
      "required_fix": "Derive enabled membership from rust_pods slot_id values (with fallback string support) instead of p_name in rust_pods_list."
    }
  ],
  "closed": []
}
```
