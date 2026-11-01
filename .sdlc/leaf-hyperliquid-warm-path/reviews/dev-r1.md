# DEV Review — Round 1

## Summary

Lane M change adds Hyperliquid warm-path wiring in `backend/agents/orchestrator.py` and a covering test. The change is otherwise consistent with prior leaf warm-path implementations, tests pass, and CI is green. One material correctness defect remains: because `rust_pods` contains dictionaries, the `PodAllocation.enabled` flags in the compiled `PolicyEnvelope` are always computed as `False`, so the named Hyperliquid pods are never marked active despite being counted for capital weights. Fix the membership comparison before approval.

## Findings

### DEV-R1-F01 — major PolicyEnvelope marks all pods disabled for real leaves
- Location: `backend/agents/orchestrator.py:319-329` (`compile_leaf_policy_envelope`)
- Evidence: `leaf_state["rust_pods"]` is a list of dicts (e.g. `{"slot_id": "pod_carry", "pod_code": "hype_hlp_funding_carry", …}`), but the code uses `enabled = p_name in rust_pods_list` where `p_name` is a string. A direct call of `compile_leaf_policy_envelope("leaf-hyperliquid")` therefore returns `pod_carry=pod_momentum=pod_onchain_alpha=pod_sniper` all with `enabled=False`, `capital_weight=0.0`. This contradicts the issue's `pod_allocations` deliverable and leaves computed `weight_per_pod` unused.
- Required fix: normalize the pod list to slot ids before membership, e.g. `pod_slot_ids = {p.get("slot_id") if isinstance(p, dict) else p for p in rust_pods_list}` and use `enabled = p_name in pod_slot_ids`, while retaining fallback string support.
- Status: open
- Origin: initial

## Checks run
- `cargo test --manifest-path engine-rs/Cargo.toml` → 119 tests passed (all crates)
- `PYTHONPATH=. python3.11 -m unittest discover -s backend/tests` → 296 tests passed
- `cd frontend && npm run build` → built successfully
- `gh pr checks 202` → frontend, helm, python, rust all pass

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-hyperliquid-warm-path",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "70d07a013fa5c4c9728187e46e2a1324e22e37f9",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Warm-path wiring is consistent and checks pass, but compiled PolicyEnvelope disables every pod because membership compares strings to dicts.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "backend/agents/orchestrator.py:319-329",
      "evidence": "Direct compile_leaf_policy_envelope('leaf-hyperliquid') returns all pod_allocations enabled=False despite rust_pods containing four dicts with slot_id.",
      "required_fix": "Derive enabled from rust_pods slot_id values (with fallback string support) instead of `p_name in rust_pods_list`."
    }
  ],
  "closed": []
}
```