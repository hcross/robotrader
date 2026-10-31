# SPEC Review — Round 1

## Summary

CHANGES_REQUESTED. The architectural direction is sound and directly resolves the core honesty and integrity defects flagged in issue #6 — pod catalog parity across Rust and Python, explicit execution and telemetry mode labelling (`ACTIVE_SOLANA` vs `PASSIVE_CATALOG`, `CATALOG_FIXTURE`), sentiment casing correction (`composite_sentiment`), dynamic confluence computation, and RSS/panorama provenance stamping. Both strict OpenSpec validation and `spec-lint.py` pass cleanly.

However, one major finding blocks approval: `specs/pod-catalog-parity/spec.md#L5` enumerates an erroneous 26-leaf list that includes 9 non-existent ecosystems (`leaf-algorand`, `leaf-arbitrum`, etc.) and omits 9 canonical ecosystems (`leaf-chainlink`, `leaf-stacks`, etc.), directly contradicting accepted ADR-0003, `backend/core/hierarchy.py`, and `engine-rs`. Two non-blocking findings (minor, nit) address missing error handling for invalid `--leaf-id` in the node CLI export and an edge-case definition for empty RSS feed summaries.

## Findings

### SPEC-R1-F01 — [major] Erroneous 26-leaf identifier list contradicts ADR-0003 taxonomy and codebase

- Location: `openspec/changes/fix-leaf-fleet-parity-honesty/specs/pod-catalog-parity/spec.md#L5`
- Evidence: Line 5 of `specs/pod-catalog-parity/spec.md` enumerates the 26 supported ecosystems as `(`leaf-solana`, `leaf-bitcoin`, `leaf-ethereum`, `leaf-bnb`, `leaf-xrp`, `leaf-ton`, `leaf-tron`, `leaf-cardano`, `leaf-avalanche`, `leaf-polkadot`, `leaf-near`, `leaf-aptos`, `leaf-sui`, `leaf-cosmos`, `leaf-algorand`, `leaf-arbitrum`, `leaf-optimism`, `leaf-base`, `leaf-polygon`, `leaf-zksync`, `leaf-starknet`, `leaf-linea`, `leaf-scroll`, `leaf-hyperliquid`, `leaf-binance-cex`, `leaf-paper-sandbox`)`. This list includes 9 ecosystems that do not exist anywhere in the platform (`leaf-algorand`, `leaf-arbitrum`, `leaf-optimism`, `leaf-base`, `leaf-polygon`, `leaf-zksync`, `leaf-starknet`, `leaf-linea`, `leaf-scroll`), and omits 9 canonical ecosystems defined in ADR-0003 (`docs/adr/0003-hierarchical-multi-ecosystem-architecture.md#L38-44`), `backend/core/hierarchy.py` (`LEAF_ECOSYSTEM_CATALOG`), and `engine-rs/crates/risk-gate/src/vault.rs#L223-423` (`leaf-chainlink`, `leaf-stacks`, `leaf-dogecoin`, `leaf-icp`, `leaf-canton`, `leaf-celo`, `leaf-tezos`, `leaf-flow`, `leaf-eos`). Implementing or testing against this requirement as written causes tests to assert against non-existent leaves and leaves 9 actual system leaves untested.
- Required fix: Update `specs/pod-catalog-parity/spec.md#L5` to replace the 9 non-existent leaf identifiers with the 9 canonical platform leaves matching ADR-0003 and `LEAF_ECOSYSTEM_CATALOG`: `leaf-chainlink`, `leaf-stacks`, `leaf-dogecoin`, `leaf-icp`, `leaf-canton`, `leaf-celo`, `leaf-tezos`, `leaf-flow`, `leaf-eos`.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [minor] Missing error specification for invalid `--leaf-id` in CLI pod catalog export

- Location: `openspec/changes/fix-leaf-fleet-parity-honesty/specs/pod-catalog-parity/spec.md#L32-L46`
- Evidence: `Requirement: Node CLI exports deterministic pod catalog` specifies output for `robotrader-node --dump-pod-catalog` (all 26 leaves) and `robotrader-node --dump-pod-catalog --leaf-id <id>` (single leaf), but does not specify behavior when `--leaf-id` is provided an unknown or invalid leaf identifier. `engine-rs/crates/strategies/src/lib.rs#L923-956` currently has a wildcard fallback `_ =>` that synthesizes generic pods for any arbitrary string, so an unknown leaf query (e.g. `--leaf-id unknown-leaf`) would exit with status code 0 and emit synthesized fallback specs instead of failing.
- Required fix: Add an explicit requirement clause and a failure scenario specifying that when `--leaf-id` is given an unrecognized leaf identifier (not among the 26 supported leaves), `robotrader-node` MUST exit with a non-zero status code and print an error message to stderr.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [nit] `feed_mode` summary behavior on empty item collection

- Location: `openspec/changes/fix-leaf-fleet-parity-honesty/specs/feed-panorama-provenance/spec.md#L60-L64`
- Evidence: Line 61 defines `feed_mode` as `"LIVE"` if all items are live, `"CURATED_FALLBACK"` if all items are curated, or `"MIXED"` if both exist. In the boundary case where `items` is empty (`live_count == 0` and `curated_count == 0`, e.g., if `max_items == 0`), `feed_mode` is ambiguous under these definitions.
- Required fix: Explicitly specify `feed_mode` when `items` is empty (e.g. `"CURATED_FALLBACK"` or `"EMPTY"`).
- Status: open
- Origin: initial

## Checks run

- `openspec validate fix-leaf-fleet-parity-honesty --strict` → pass (exit 0)
- `python3 scripts/sdlc/spec-lint.py --change fix-leaf-fleet-parity-honesty` → pass (Review Card 152 words, 1 diagram, ~1.3 min, lane L)
- Read time: ~1.3 min, well within the ≤ 5.0 min budget

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "fix-leaf-fleet-parity-honesty",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "7c7d21d2c5448239386876dcd023c1ef66082680",
  "verdict": "CHANGES_REQUESTED",
  "summary": "The proposal and capabilities are architecturally sound, but pod-catalog-parity spec enumerates 9 non-existent ecosystems while omitting 9 canonical ADR-0003 leaves, blocking approval.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-leaf-fleet-parity-honesty/specs/pod-catalog-parity/spec.md#L5",
      "evidence": "Line 5 of specs/pod-catalog-parity/spec.md enumerates 26 supported ecosystems including 9 non-existent chains (leaf-algorand, leaf-arbitrum, leaf-optimism, leaf-base, leaf-polygon, leaf-zksync, leaf-starknet, leaf-linea, leaf-scroll) and omits 9 canonical ecosystems defined in ADR-0003, LEAF_ECOSYSTEM_CATALOG, and vault.rs (leaf-chainlink, leaf-stacks, leaf-dogecoin, leaf-icp, leaf-canton, leaf-celo, leaf-tezos, leaf-flow, leaf-eos).",
      "required_fix": "Update specs/pod-catalog-parity/spec.md#L5 to replace the 9 non-existent leaf identifiers with the 9 canonical platform leaves matching ADR-0003 and LEAF_ECOSYSTEM_CATALOG: leaf-chainlink, leaf-stacks, leaf-dogecoin, leaf-icp, leaf-canton, leaf-celo, leaf-tezos, leaf-flow, leaf-eos."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-leaf-fleet-parity-honesty/specs/pod-catalog-parity/spec.md#L32-L46",
      "evidence": "Requirement: Node CLI exports deterministic pod catalog specifies output for robotrader-node --dump-pod-catalog and --leaf-id <id>, but lacks error handling specification when --leaf-id is unknown. In strategies/src/lib.rs, wildcard fallback _ => would synthesize fallback pods for any string and exit 0 instead of failing loudly.",
      "required_fix": "Add an explicit requirement clause and a failure scenario specifying that when --leaf-id is given an unrecognized leaf identifier (not among the 26 supported leaves), robotrader-node MUST exit with a non-zero status code and print an error message to stderr."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/fix-leaf-fleet-parity-honesty/specs/feed-panorama-provenance/spec.md#L60-L64",
      "evidence": "Line 61 defines feed_mode as LIVE if all items are live, CURATED_FALLBACK if all items are curated, or MIXED if both exist. When items is empty (live_count == 0 and curated_count == 0), feed_mode behavior is unstated.",
      "required_fix": "Explicitly specify feed_mode when items is empty (e.g. CURATED_FALLBACK or EMPTY)."
    }
  ],
  "closed": []
}
```
