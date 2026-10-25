stage: spec
round: 1
head_sha: 7fbba923abee0906c69c0c2bd2ce78d7f6868d73
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: "Corrected the count to eight: `specs/contract/spec.md` §Complete AssetOverride field parity now enumerates the eight absent fields including `min_rsi_short`; `proposal.md` Review Card, Why, What Changes, and Impact now say eight. Impact adds `AGENTS.md`/`README.md` as documentation deliverables that must list all eleven keys including `min_rsi_short`. The spec author does not edit docs; the update is carried as a DEV-stage Impact deliverable."
  - id: SPEC-R1-F02
    action: fixed
    evidence: "`proposal.md` Review Card Risk and §Impact Risk/money now state that the OBI gate loosens from 0.22/0.18 to 0.08 for override-bearing symbols while RSI, support/resistance, and invalidation gates tighten when their inputs exist. The breaking surface is now stated as strict policy decoding. The 'required rsi_14 decode break' half is superseded by F04, which chooses the optional-field resolution and therefore removes that break."
  - id: SPEC-R1-F03
    action: fixed
    evidence: "`specs/contract/spec.md` §Single-sourced safe-baseline TTL now defines the predicate: exactly one declaration of the named key `SAFE_BASELINE_TTL_SECONDS` in a single machine-readable contract file, value 900; both `safe_baseline()` constructors resolve from it; `from_dict` and `default_active` are explicit check exemptions. The negative scenario now introduces a second declaration of that named key and asserts the check exits non-zero naming the duplicate file."
  - id: SPEC-R1-F04
    action: fixed
    evidence: "`specs/contract/spec.md` §Optional RSI input on MarketEvent now makes `rsi_14` optional (`Option<f64>` + `#[serde(default)]`), removes the false warm-path provenance claim, and states that today only the Rust backtest fixtures produce `OrderbookTick`. The RSI guard is explicitly observable: a scenario requires `RSI=INACTIVE` in `OrderIntent.rationale` when `rsi_14` is absent. `proposal.md` §Non-goals defers the warm-path producer/transport to a follow-up issue."
  - id: SPEC-R1-F05
    action: fixed
    evidence: "`specs/contract/spec.md` §Strict policy decoding now states that `MarketEvent` and `OnChainTokenSafety` keep serde's default tolerant behaviour and MUST NOT receive `deny_unknown_fields`. New scenario 'Unknown event field remains tolerated' pins the boundary."
  - id: SPEC-R1-F06
    action: fixed
    evidence: "`specs/contract/spec.md` §Complete AssetOverride field parity now states that `catalyst_score`, `bias`, and `max_leverage` remain required non-`Option` fields, and scenario 'Missing required field is rejected' asserts decoding fails when any of the three is omitted."
  - id: SPEC-R1-F07
    action: fixed
    evidence: "Scenario 'Absent optional rule decodes' now says 'an envelope JSON from a non-Python or older producer omits `entry_obi_threshold`' and explicitly notes that the Python `to_dict()` path always emits all eleven keys."
  - id: SPEC-R1-F08
    action: fixed
    evidence: "`proposal.md` §Impact names `backend/tests/test_architecture.py::test_python_to_rust_backtest_bridge_and_regime_switching` and its `total_trades == 6`, `rejected_orders == 1`, and `total_trades == 4` assertions, and requires the DEV stage to preserve them by deliberate fixture choice or re-baseline them with the Rust backtest output attached as evidence."
  - id: SPEC-R1-F09
    action: fixed
    evidence: "Added boundary scenarios: 'OBI boundary is inclusive', 'Support boundary is inclusive', 'Resistance boundary is inclusive', 'Invalidation gate blocks a short at the level', and 'Short RSI boundary is inclusive'; the existing long RSI and long invalidation boundaries remain. Every `>=`, `<=`, `>`, and `<` convention is now pinned."
  - id: SPEC-R1-F10
    action: fixed
    evidence: "`proposal.md` §Non-goals now declares `pod_solana_alpha` -> `pod_onchain_alpha` canonicalisation across Python maps and Rust `HashMap` keys a follow-up issue/ADR."
  - id: SPEC-R1-F11
    action: fixed
    evidence: "`proposal.md` §Impact now lists `AGENTS.md` and `README.md` as documentation deliverables and adds `backend/core/state_store.py` for the warm-path short-RSI alignment required by F13. Producer files are not listed because F04 deliberately adds no warm-path transport."
  - id: SPEC-R1-F12
    action: fixed
    evidence: "Review Card Outcome now reads 'gate momentum entries, and populate TP/SL distances'; Effort is now 'Medium — one SPEC round, one PLAN round, one DEV round' instead of 'M'."
  - id: SPEC-R1-F13
    action: fixed
    evidence: "`specs/contract/spec.md` §Momentum pod applies envelope mechanical rules now makes `min_rsi_short` authoritative and forbids the `100.0 - max_rsi_long` derivation in the warm-path paper model. Scenario 'Warm-path short RSI uses min_rsi_short' pins the shared threshold. `proposal.md` §What Changes and §Impact carry the alignment."
