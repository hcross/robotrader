# SPEC Review — Round 2

## Summary

APPROVE. All 13 R1 findings are closed at `5bc41cd`, and the three stage checks pass. The field count is now eight missing plus three required with no residual "seven"; the OBI loosening and the strict-decode break are stated coherently in both Risk rows; `rsi_14` is optional with an observable `RSI=INACTIVE` path, and the warm-path producer is an explicit non-goal; the TTL predicate names `SAFE_BASELINE_TTL_SECONDS`, exempts `from_dict`/`default_active`, and specifies a duplicate-file check; every boundary convention has a scenario; warm-path `min_rsi_short`, the `pod_solana_alpha` non-goal, the documentation Impact, and the exact bridge-test counts are present. No regression, security, or critical finding was introduced by the revision.

### Non-blocking follow-ups (not findings, do not block)

- The `|OBI| >= entry_obi_threshold` phrasing predates R1 and can be read as permitting a long with strongly negative OBI. PLAN/DEV should pin the directional form: long `OBI >= t`, short `OBI <= -t` (`engine-rs/crates/strategies/src/lib.rs#L155-L192`).
- Impact does not name the new shared contract file or the repository-check script implied by the TTL requirement; PLAN should name both.
- The round-trip test's "part of the standard suites" clause needs a transport decision (committed Python-produced fixture vs. Python-driven Rust binary) in PLAN.
- The Risk row says "an older envelope with an unknown key halts the hot path"; a missing required key also halts (scenario `Missing required field is rejected`); broadening the wording would match the requirement exactly.

## Findings

### SPEC-R1-F01 — [major] "Seven" missing keys contradict the eight enumerated keys
- Location: `openspec/changes/align-asset-override-contract/specs/contract/spec.md#L5`; `proposal.md#L5,L6,L22,L28`
- Evidence: The requirement and proposal now say "eight" everywhere (`grep -rn seven` returns no match) and enumerate all eight absent keys, including `min_rsi_short`; Python declares eleven fields and Rust three.
- Required fix: Replace "seven" with "eight" and add `min_rsi_short` to the `AGENTS.md` field list.
- Status: closed
- Origin: initial

### SPEC-R1-F02 — [major] Risk statement reverses the OBI effect and omits the `rsi_14` break
- Location: `proposal.md#L8` (Risk row) and `#L63` (Risk/money bullet)
- Evidence: Both rows now state that the OBI gate loosens from 0.22/0.18 to 0.08 for override-bearing symbols while RSI, zone, and invalidation gates tighten, and that strict policy decoding is the breaking surface. The former required-`rsi_14` break is superseded by the F04 optional-field resolution endorsed in the round-2 brief; the Risk row and `Strict policy decoding` / `Fail-loud CLI` requirements agree.
- Required fix: Rewrite the Risk rows to state the OBI loosening and the breaking strict decode.
- Status: closed
- Origin: initial

### SPEC-R1-F03 — [major] Safe-baseline "single source" and duplicate check have no verifiable predicate
- Location: `specs/contract/spec.md#L215-L237`
- Evidence: The requirement now names `SAFE_BASELINE_TTL_SECONDS` as the sole declaration in one machine-readable contract file (value 900), requires both `safe_baseline()` constructors to resolve from it, exempts `from_dict`/`default_active`, and requires the check to exit non-zero naming a second declaring file. The negative scenario introduces that exact duplicate and asserts the named failure, so the predicate is observable.
- Required fix: Define the observable predicate and make the duplicate scenario concrete.
- Status: closed
- Origin: initial

### SPEC-R1-F04 — [major] `rsi_14` provenance ("computed by the warm path") has no producer
- Location: `specs/contract/spec.md#L86-L99`; `proposal.md#L30,L53`
- Evidence: `rsi_14` is now `Option<f64>` with `#[serde(default)]`; the requirement states no warm-path producer/transport is added and that only the Rust backtest fixtures produce `OrderbookTick` (verified: the only constructors are `engine-rs/crates/backtest/src/lib.rs#L255,L304,L421`). Non-goals defer the producer. The `RSI=INACTIVE` scenario makes the absent path observable in `OrderIntent.rationale`.
- Required fix: Name the producer or reword to optional + Non-goal.
- Status: closed
- Origin: initial

### SPEC-R1-F05 — [minor] Strict-decoding boundary is not explicit for `MarketEvent`/`OnChainTokenSafety`
- Location: `specs/contract/spec.md#L42`, `#L65-L68`
- Evidence: The requirement now states that `MarketEvent` and `OnChainTokenSafety` retain serde's default tolerant behaviour and MUST NOT receive `deny_unknown_fields`, and scenario `Unknown event field remains tolerated` pins it.
- Required fix: Add the tolerant-boundary sentence or Non-goal and a scenario.
- Status: closed
- Origin: initial

### SPEC-R1-F06 — [minor] Requiredness of `catalyst_score`, `bias`, `max_leverage` is not pinned
- Location: `specs/contract/spec.md#L5`, `#L25-L28`
- Evidence: The requirement states the three fields are required non-`Option`; scenario `Missing required field is rejected` asserts decoding fails and names the omitted field.
- Required fix: State requiredness and add the missing-field scenario.
- Status: closed
- Origin: initial

### SPEC-R1-F07 — [minor] "Python envelope omits" is impossible with `asdict`
- Location: `specs/contract/spec.md#L19-L23`
- Evidence: The scenario now says "an envelope JSON from a non-Python or older producer" and notes that `to_dict()` always emits all eleven keys (`backend/core/schemas.py#L34-L35`).
- Required fix: Reword to envelope JSON and state the producer caveat.
- Status: closed
- Origin: initial

### SPEC-R1-F08 — [minor] Migration plan does not name the existing exact-count assertions
- Location: `proposal.md#L64`
- Evidence: Impact now names `backend/tests/test_architecture.py::test_python_to_rust_backtest_bridge_and_regime_switching` with `total_trades == 6`, `rejected_orders == 1`, and `total_trades == 4`, and requires DEV to preserve them or re-baseline with attached Rust backtest output. The assertions match `backend/tests/test_architecture.py#L38-L56`.
- Required fix: Add the test and its exact counts to Impact with a preserve/re-baseline rule.
- Status: closed
- Origin: initial

### SPEC-R1-F09 — [minor] Missing boundary scenarios for the inclusive/strict gates
- Location: `specs/contract/spec.md#L110-L169`
- Evidence: The added scenarios cover `OBI == entry_obi_threshold` (L110), `mid == support` (L146), `mid == resistance` (L156), short `mid == invalidation` (L166), and `rsi_14 == min_rsi_short` (L130); the long RSI and long invalidation boundaries remain.
- Required fix: Add the missing boundary scenarios.
- Status: closed
- Origin: initial

### SPEC-R1-F10 — [minor] Pod-key canonicalisation is neither in scope nor a Non-goal
- Location: `proposal.md#L54`
- Evidence: Non-goals now declare `pod_solana_alpha` → `pod_onchain_alpha` canonicalisation across Python maps and Rust `HashMap` keys a follow-up issue/ADR.
- Required fix: Add it to Non-goals or bring it into scope.
- Status: closed
- Origin: initial

### SPEC-R1-F11 — [minor] Impact omits the documentation that states the repaired contract
- Location: `proposal.md#L60-L65`
- Evidence: Impact now lists `AGENTS.md` and `README.md` as documentation deliverables that MUST list all eleven keys including `min_rsi_short`, and adds `backend/core/state_store.py` for the F13 alignment.
- Required fix: List the documentation files and producer files.
- Status: closed
- Origin: initial

### SPEC-R1-F12 — [nit] Outcome overstates TP/SL and "Effort: M" collides with lane vocabulary
- Location: `proposal.md#L5`, `#L9`
- Evidence: The Outcome now reads "gate momentum entries, and populate TP/SL distances"; Effort is "Medium — one SPEC round, one PLAN round, one DEV round".
- Required fix: Reword the Outcome and replace "M" with "Medium".
- Status: closed
- Origin: initial

### SPEC-R1-F13 — [minor] Short-RSI semantics diverge between warm path and the new hot-path rule
- Location: `specs/contract/spec.md#L103`, `#L187-L191`; `proposal.md#L32`
- Evidence: The requirement makes `min_rsi_short` authoritative for the warm-path paper model and forbids the `100.0 - max_rsi_long` derivation (present today at `backend/core/state_store.py#L463-L464`); scenario `Warm-path short RSI uses min_rsi_short` pins the shared threshold, and `state_store.py` is in Impact.
- Required fix: State the authoritative semantics and require the warm-path alignment.
- Status: closed
- Origin: initial

## Checks run

- `openspec validate align-asset-override-contract --strict` → `Change 'align-asset-override-contract' is valid` (exit 0)
- `scripts/sdlc/spec-lint.py --change align-asset-override-contract` → PASS; Review Card 147 words, 1 diagram, ~1.2 min
- `scripts/sdlc/sdlc.sh check align-asset-override-contract` → `check: PASS` (openspec pass, spec-lint pass, prior r1 recognized)
- `scripts/sdlc/verdict-lint.py --change align-asset-override-contract` → PASS after this file is written
- Artifact reviewed at `5bc41cddcf0ec84c9901bfe89cf68e959fc786b9`; `git diff HEAD -- openspec/changes/align-asset-override-contract` is empty
- Review Card read time: 1.2 min (spec-lint); full closure review: ~14 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "spec",
  "round": 2,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "5bc41cddcf0ec84c9901bfe89cf68e959fc786b9",
  "verdict": "APPROVE",
  "summary": "All 13 R1 findings are closed at 5bc41cd; no regression, security, or critical issue was introduced, and the three stage checks pass.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L5; proposal.md#L5,L6,L22,L28",
      "evidence": "All references now say eight and enumerate the eight absent keys including min_rsi_short; grep for 'seven' returns no match.",
      "required_fix": "Replace 'seven' with 'eight' and add min_rsi_short to the AGENTS.md field list."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L8; proposal.md#L63",
      "evidence": "Both Risk rows state the OBI gate loosens from 0.22/0.18 to 0.08 for override-bearing symbols while RSI/zone/invalidation gates tighten, and that strict decoding is the breaking surface; the rsi_14 break is superseded by the F04 optional-field resolution.",
      "required_fix": "Rewrite the Risk rows to state the OBI loosening and the breaking strict decode."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L215-L237",
      "evidence": "SAFE_BASELINE_TTL_SECONDS is the sole declaration (value 900); both safe_baseline() constructors resolve it; from_dict/default_active are explicit exemptions; a second declaration makes the check exit non-zero naming the duplicate file.",
      "required_fix": "Define the observable predicate and make the duplicate scenario concrete."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L86-L99; proposal.md#L30,L53",
      "evidence": "rsi_14 is Option<f64> with serde(default); the spec states no warm-path producer is added and only the Rust backtest fixtures produce OrderbookTick (backtest/src/lib.rs#L255,L304,L421); the producer is a Non-goal; RSI=INACTIVE is an observable scenario.",
      "required_fix": "Name the producer or reword to optional plus Non-goal."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L42, #L65-L68",
      "evidence": "The requirement keeps MarketEvent and OnChainTokenSafety tolerant and forbids deny_unknown_fields; a scenario pins it.",
      "required_fix": "Add the tolerant-boundary sentence and scenario."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L5, #L25-L28",
      "evidence": "catalyst_score, bias, and max_leverage are stated required non-Option; the missing-required-field scenario asserts a named decode failure.",
      "required_fix": "State requiredness and add the missing-field scenario."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L19-L23",
      "evidence": "The scenario now refers to an envelope JSON from a non-Python or older producer and notes that to_dict always emits all eleven keys.",
      "required_fix": "Reword to envelope JSON and state the producer caveat."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L64",
      "evidence": "Impact names backend/tests/test_architecture.py::test_python_to_rust_backtest_bridge_and_regime_switching with total_trades == 6, rejected_orders == 1, and total_trades == 4, and requires preserve-or-rebaseline with evidence.",
      "required_fix": "Add the test and exact counts to Impact with a preserve/re-baseline rule."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L110-L169",
      "evidence": "Scenarios cover OBI equality, support equality, resistance equality, short invalidation equality, and short RSI equality; long boundaries remain.",
      "required_fix": "Add the missing boundary scenarios."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L54",
      "evidence": "Non-goals now defer pod_solana_alpha to pod_onchain_alpha canonicalisation to a follow-up issue/ADR.",
      "required_fix": "Add the canonicalisation to Non-goals or scope it explicitly."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L60-L65",
      "evidence": "Impact lists AGENTS.md and README.md as documentation deliverables and adds backend/core/state_store.py for the warm-path alignment.",
      "required_fix": "List the documentation and producer files."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "nit",
      "origin": "initial",
      "status": "closed",
      "location": "proposal.md#L5, #L9",
      "evidence": "Outcome reads 'gate momentum entries, and populate TP/SL distances'; Effort reads 'Medium'.",
      "required_fix": "Reword the Outcome and replace 'M' with 'Medium'."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "closed",
      "location": "specs/contract/spec.md#L103, #L187-L191; proposal.md#L32",
      "evidence": "The requirement makes min_rsi_short authoritative and forbids 100.0 - max_rsi_long (present at backend/core/state_store.py#L463-L464); a scenario pins the shared threshold and state_store.py is in Impact.",
      "required_fix": "State the authoritative semantics and require the warm-path alignment."
    }
  ],
  "closed": [
    "SPEC-R1-F01",
    "SPEC-R1-F02",
    "SPEC-R1-F03",
    "SPEC-R1-F04",
    "SPEC-R1-F05",
    "SPEC-R1-F06",
    "SPEC-R1-F07",
    "SPEC-R1-F08",
    "SPEC-R1-F09",
    "SPEC-R1-F10",
    "SPEC-R1-F11",
    "SPEC-R1-F12",
    "SPEC-R1-F13"
  ]
}
```
