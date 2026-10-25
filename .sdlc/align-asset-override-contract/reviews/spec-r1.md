# SPEC Review — Round 1

## Summary

CHANGES_REQUESTED. The artifact targets the real drift and all stage checks pass, but four majors leave the contract untrustworthy as written. (1) The parity requirement says "seven" missing keys while enumerating eight; Python has eleven fields against Rust's three. (2) The proposal calls the entry change "more restrictive" although the effective OBI gate loosens from 0.22/0.18 to 0.08 for override-bearing symbols, and it omits the breaking `rsi_14` decode. (3) "Single authoritative definition" and its duplicate-detection check have no verifiable predicate; Python holds three 900 literals. (4) `rsi_14` is said to be "computed by the warm path", but no warm-path producer of `OrderbookTick` exists. Eight minors and one nit are also recorded. Round 2 should verify these fixes only.

## Checklist walk (`sdlc/checklists/spec.md`)

| § | Item | Result | Ref |
|---|---|---|---|
| 1 | Review Card states outcome in one understandable line | PASS | F12 nit on wording |
| 1 | Why now, blast radius, risk, effort, decision needed | PASS | present; F02 covers risk accuracy |
| 1 | ≤ 400 words with ≥ 1 diagram | PASS | 114 words, 1 Mermaid diagram |
| 1 | Read time ≤ 5.0 min | PASS | spec-lint: ~1.1 min |
| 1 | No prose wall | PASS | tables + bullets; paragraphs ≤ 2 sentences |
| 1 | Non-goals present and meaningful | PASS | F10 requests one more non-goal |
| 2 | Problem is an observed fact | PASS | issue #10 evidence + `schemas.py:21-32` vs `lib.rs:158-162` |
| 2 | Scope boundary clear | FAIL | F03, F04 |
| 2 | Right-sized for lane | PASS | lane L: breaking contract, Rust+Python |
| 2 | No hidden second change | PASS | TTL is in the #10 triage scope comment |
| 3 | One delta file per capability | PASS | `contract` → `specs/contract/spec.md` |
| 3 | ADDED/MODIFIED/REMOVED/RENAMED used correctly | PASS | all ADDED under a new capability |
| 3 | MODIFIED copies entire block | N/A | no MODIFIED requirements |
| 3 | REMOVED carries reason + migration | N/A | no REMOVED requirements |
| 3 | Requirement/scenario names unique and stable | PASS | verified by inspection |
| 4 | Every requirement uses SHALL/MUST | PASS | all eight requirements |
| 4 | Every requirement observable and testable | FAIL | F03, F04 |
| 4 | No implementation prescription unless a real constraint | PASS | `Option` + serde attributes are the contract's optionality/null constraint |
| 4 | No vague words without measurable definition | FAIL | F03 ("authoritative definition") |
| 4 | No TBD/TODO/???/open question | PASS | none found |
| 5 | Every requirement has ≥ 1 scenario | PASS | 8/8 |
| 5 | Every scenario has WHEN and THEN | PASS | verified by inspection |
| 5 | Happy, failure, boundary paths covered | FAIL | F09, plus F04/F06 |
| 5 | Scenarios independent | PASS | one behaviour per scenario |
| 5 | THEN is observable, not an internal call | PASS | intent emitted / decode error / exit status |
| 6 | No contradiction with existing spec | PASS | `openspec/specs/health/spec.md` unrelated |
| 6 | No contradiction with accepted ADR | PASS | upholds ADR-0001 strict-sync discipline |
| 6 | Contract impact identified | PASS | PolicyEnvelope/MarketEvent/`--policy-json`; no REST/WS/DB |
| 6 | Money/risk/vault/hot-path impact identified | FAIL | F02 |
| 6 | Backtest/paper/live implications identified | PASS | F08 asks for the specific test |
| 6 | Multi-chain/venue isolation addressed | PASS | per-symbol overrides; leaf isolation unchanged |
| 7 | Impact lists real files/services/contracts | FAIL | F04, F08, F11 |
| 7 | Acceptance criterion maps to scenario | PASS | each requirement has scenarios |
| 7 | Task list maps to scenarios/invariants | N/A | `tasks.md` is PLAN for lane L |
| 7 | Verifiable without the author's chat | FAIL | warm-path provenance (F04) |

## Findings

### SPEC-R1-F01 — [major] "Seven" missing keys contradict the eight enumerated keys
- Location: `openspec/changes/align-asset-override-contract/specs/contract/spec.md#L5`; `proposal.md#L5`, `#L6`, `#L22`, `#L28`
- Evidence: The requirement says "The seven mechanical-rule keys absent from the current Rust type SHALL be `Option<T>`" and then enumerates eight keys, including `min_rsi_short`. Python declares eleven `AssetOverride` fields (`backend/core/schemas.py#L21-L32`) and Rust declares three (`engine-rs/crates/common/src/lib.rs#L158-L162`), so eight are missing. The proposal repeats "seven of eleven" (L6) and "the other seven" (L22).
- Required fix: Replace "seven" with "eight" in `spec.md#L5` and `proposal.md#L5,L6,L22,L28` (or reword to "the eight keys not present in the current Rust type"), and add `min_rsi_short` to the `AGENTS.md` field list the issue quotes so the documented contract matches the normative list.
- Status: open
- Origin: initial

### SPEC-R1-F02 — [major] Risk statement reverses the OBI effect and omits the `rsi_14` break
- Location: `proposal.md#L8` (Risk row) and `#L60` (Risk/money bullet)
- Evidence: The proposal says "momentum entries become more restrictive", but `entry_obi_threshold` defaults to 0.08 (`backend/core/schemas.py#L28`; `backend/agents/orchestrator.py#L445` clamps default 0.08), while the pod's configured threshold is 0.22 (`engine-rs/crates/strategies/src/lib.rs#L107`) and 0.18 for ecosystem pods (`#L912`). For override-bearing symbols the OBI gate therefore loosens (0.22/0.18 → 0.08); only the RSI, zone, and invalidation gates tighten. The Risk row (L8) also omits the breaking required-`rsi_14` decode change.
- Required fix: Rewrite the Risk and Risk/money bullets to state that the OBI gate loosens for override-bearing symbols while the RSI/zone/invalidation gates tighten, and name the required `rsi_14` decode break together with its producer migration.
- Status: open
- Origin: initial

### SPEC-R1-F03 — [major] Safe-baseline "single source" and duplicate check have no verifiable predicate
- Location: `specs/contract/spec.md#L158-L180`, especially L160 and the "Duplicate definition is rejected" scenario (L177-L180)
- Evidence: "One authoritative definition" and "a second authoritative definition" are undefined. Python holds three `900` literals: `backend/core/schemas.py#L76` (`from_dict` default), `#L88` (`safe_baseline`), and `#L129` (`default_active`); only L88 is the safe-baseline TTL. As written, a repository check cannot distinguish the safe-baseline definition from the two other legitimate 900s, so the negative scenario is not testable.
- Required fix: Define the observable predicate — e.g. one named constant/file is the sole declaration of the safe-baseline TTL, both runtimes resolve it, and `from_dict`/`default_active` either derive from it or are explicitly exempt — and make the scenario concrete: introduce a second declaration of the named source and assert the check exits non-zero.
- Status: open
- Origin: initial

### SPEC-R1-F04 — [major] `rsi_14` provenance ("computed by the warm path") has no producer
- Location: `specs/contract/spec.md#L69-L81`; `proposal.md#L30`, `#L61`
- Evidence: The requirement makes `rsi_14` "computed by the warm path" a required field, but no Python code publishes `MarketEvent::OrderbookTick` (no `event_type` producer exists in `backend/`); the only producers are the Rust fixtures at `engine-rs/crates/backtest/src/lib.rs#L255`, `#L304`, and `#L421`. `backend/tools/ta_tools.py#L28-L50` computes `rsi_14` but nothing transports it into an `OrderbookTick`, and the Impact (L61) lists only fixtures.
- Required fix: Either name the warm-path producer/transport file to change and add a scenario asserting the published tick carries the warm-path RSI, or reword the requirement to "carried on `OrderbookTick` (supplied by the tick producer; today only the Rust fixtures)" and add warm-path→hot-path transport to Non-goals.
- Status: open
- Origin: initial

### SPEC-R1-F05 — [minor] Strict-decoding boundary is not explicit for `MarketEvent`/`OnChainTokenSafety`
- Location: `specs/contract/spec.md#L28-L30`
- Evidence: The requirement names only `PolicyEnvelope`, `PodAllocation`, and `AssetOverride`. It does not say that `MarketEvent` and `OnChainTokenSafety` must stay tolerant of unknown fields, so an implementer could apply `deny_unknown_fields` to all serde types and break forward-compatible event ingestion.
- Required fix: Add one sentence (or a Non-goal) stating that `MarketEvent` and `OnChainTokenSafety` keep serde's default tolerant behaviour and MUST NOT receive `deny_unknown_fields` in this change.
- Status: open
- Origin: initial

### SPEC-R1-F06 — [minor] Requiredness of `catalyst_score`, `bias`, `max_leverage` is not pinned
- Location: `specs/contract/spec.md#L5`, `#L48-L61`
- Evidence: The requirement says the eight new keys are `Option<T>` but never states that the three existing fields stay required and non-`Option`; no scenario asserts that omitting one of them fails decoding. The CLI "missing key" scenario (L59) is generic and does not pin the type-level contract.
- Required fix: State explicitly that `catalyst_score`, `bias`, and `max_leverage` remain required (non-`Option`), and add a scenario where an `AssetOverride` JSON omits `catalyst_score` and decoding fails.
- Status: open
- Origin: initial

### SPEC-R1-F07 — [minor] "Python envelope omits" is impossible with `asdict`
- Location: `specs/contract/spec.md#L14-L16`
- Evidence: The scenario says "a Python envelope omits `entry_obi_threshold`", but Python's `AssetOverride.to_dict()` uses `asdict` and always emits all eleven keys (`backend/core/schemas.py#L34-L35`). Only hand-written or older-producer JSON can omit the key.
- Required fix: Reword to "an envelope JSON omits ..." and state that this tolerates non-Python or older producers.
- Status: open
- Origin: initial

### SPEC-R1-F08 — [minor] Migration plan does not name the existing exact-count assertions
- Location: `proposal.md#L57`, `#L61`; `backend/tests/test_architecture.py#L38-L54`
- Evidence: Impact says "fixture-backed trade counts may change" but does not name the existing assertions `total_trades == 6`, `rejected_orders == 1`, and `total_trades == 4`. If the new gates change momentum entries, those assertions fail and the plan must decide whether to re-baseline or preserve them.
- Required fix: Add the Python bridge test and its exact counts to Impact, and require the expected values be re-baselined with evidence or preserved by deliberate fixture choice.
- Status: open
- Origin: initial

### SPEC-R1-F09 — [minor] Missing boundary scenarios for the inclusive/strict gates
- Location: `specs/contract/spec.md#L97-L120`
- Evidence: Boundary semantics are declared (`>=` for support/resistance, `>`/`<` for invalidation), but only the long RSI inclusive boundary and the long invalidation equality are scenario-tested. No scenario covers `mid == support`, `mid == resistance`, short `mid == invalidation`, `|OBI| == entry_obi_threshold`, or `rsi_14 == min_rsi_short`.
- Required fix: Add the missing boundary scenarios (or one table-driven boundary scenario) so every inclusive/strict convention is pinned.
- Status: open
- Origin: initial

### SPEC-R1-F10 — [minor] Pod-key canonicalisation is neither in scope nor a Non-goal
- Location: `proposal.md#L46-L53`
- Evidence: Issue #10's third secondary manifestation — Python `from_dict` canonicalises `pod_solana_alpha` → `pod_onchain_alpha` (`backend/core/schemas.py#L67`), while Rust's `PodId` serde alias cannot apply to `HashMap<String, PodAllocation>` keys — is not in the #10.1–#10.5 scope and is not listed in Non-goals.
- Required fix: Add pod-key canonicalisation to Non-goals as a follow-up issue/ADR, or bring it into scope explicitly.
- Status: open
- Origin: initial

### SPEC-R1-F11 — [minor] Impact omits the documentation that states the repaired contract
- Location: `proposal.md#L55-L62`
- Evidence: `AGENTS.md` and `README.md` are the surfaces that assert the "compiled mechanical rules" contract quoted by the issue, but neither appears in Impact. `backend/core/state_store.py` and `backend/agents/orchestrator.py` are also absent if F04 is fixed by wiring the warm-path transport.
- Required fix: List the documentation files that must be updated (or add them to Non-goals), and add the producer files if F04 is resolved by wiring the transport.
- Status: open
- Origin: initial

### SPEC-R1-F12 — [nit] Outcome overstates TP/SL and "Effort: M" collides with lane vocabulary
- Location: `proposal.md#L5`, `#L9`
- Evidence: The outcome says the rules "gate momentum entries", but TP/SL are only written into the intent; enforcement is issue #4 and is a Non-goal (L49). The Effort value "M" collides with the lane names M/S/L while this change is lane L.
- Required fix: Reword to "gate momentum entries and populate TP/SL distances"; write "Medium" (or an estimate) instead of "M".
- Status: open
- Origin: initial

### SPEC-R1-F13 — [minor] Short-RSI semantics diverge between warm path and the new hot-path rule
- Location: `specs/contract/spec.md#L85`; `backend/core/state_store.py#L461-L464`
- Evidence: The spec makes `min_rsi_short` the short RSI guard, while the warm-path paper execution model uses `100.0 - max_rsi_long` as the short RSI threshold. The same override therefore has two short-RSI semantics across runtimes — the display-versus-execution drift class this change targets.
- Required fix: State which semantics is authoritative and require the warm-path evaluation to use `min_rsi_short`, or document the divergence and why it is intentional.
- Status: open
- Origin: initial

## Checks run

- `openspec validate align-asset-override-contract --strict` → `Change 'align-asset-override-contract' is valid` (exit 0)
- `scripts/sdlc/spec-lint.py --change align-asset-override-contract` → PASS; Review Card 114 words, 1 diagram, ~1.1 min; warnings for absent `design.md`/`tasks.md` are expected at SPEC for lane L
- `scripts/sdlc/sdlc.sh check align-asset-override-contract` → `check: PASS` (openspec pass, spec-lint pass, no prior verdicts)
- Artifact reviewed at `7fbba923abee0906c69c0c2bd2ce78d7f6868d73`; `git diff HEAD -- openspec/changes/align-asset-override-contract` is empty
- Review Card read time: 1.1 min (spec-lint); full artifact review: ~22 min

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "align-asset-override-contract",
  "stage": "spec",
  "round": 1,
  "reviewer": "sdlc-spec-reviewer",
  "reviewed_sha": "7fbba923abee0906c69c0c2bd2ce78d7f6868d73",
  "verdict": "CHANGES_REQUESTED",
  "summary": "Four majors: the field count contradicts the enumerated keys; the risk statement reverses the OBI effect and omits the rsi_14 break; the TTL duplicate-detection check has no verifiable predicate; and rsi_14 has no warm-path producer.",
  "findings": [
    {
      "id": "SPEC-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L5; proposal.md#L5,L6,L22,L28",
      "evidence": "The requirement says 'seven mechanical-rule keys absent' but enumerates eight, including min_rsi_short. Python has 11 fields (backend/core/schemas.py#L21-L32) and Rust has 3 (engine-rs/crates/common/src/lib.rs#L158-L162), so 8 are missing; the proposal repeats 'seven of eleven' and 'the other seven'.",
      "required_fix": "Replace 'seven' with 'eight' in spec.md#L5 and proposal.md#L5,L6,L22,L28, or reword to 'the eight keys not present in the current Rust type'; add min_rsi_short to the AGENTS.md field list."
    },
    {
      "id": "SPEC-R1-F02",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L8; proposal.md#L60",
      "evidence": "'momentum entries become more restrictive' is false for OBI: entry_obi_threshold defaults to 0.08 (backend/core/schemas.py#L28; backend/agents/orchestrator.py#L445) versus the pod's 0.22 (engine-rs/crates/strategies/src/lib.rs#L107) or 0.18 (L912), so the override loosens the OBI gate. The Risk row also omits the breaking required rsi_14 decode.",
      "required_fix": "State that the OBI gate loosens for override-bearing symbols while RSI/zone/invalidation gates tighten, and name the required rsi_14 decode break with its producer migration."
    },
    {
      "id": "SPEC-R1-F03",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L158-L180",
      "evidence": "'authoritative definition' has no defined predicate. Python has 900 at backend/core/schemas.py#L76 (from_dict default), #L88 (safe_baseline), and #L129 (default_active); only L88 is the safe-baseline TTL, so the duplicate-detection check cannot distinguish them as written.",
      "required_fix": "Define the observable predicate (one named source, both runtimes derive, from_dict/default_active exempt or derived) and make the negative scenario concrete by introducing a second declaration of that named source and asserting the check fails."
    },
    {
      "id": "SPEC-R1-F04",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L69-L81; proposal.md#L30,L61",
      "evidence": "The requirement says rsi_14 is 'computed by the warm path', but no Python code publishes MarketEvent::OrderbookTick; the only producers are engine-rs/crates/backtest/src/lib.rs#L255,L304,L421. backend/tools/ta_tools.py#L28-L50 computes RSI but nothing transports it, and Impact lists only fixtures.",
      "required_fix": "Name the warm-path producer/transport to change and add a scenario, or reword to 'carried on OrderbookTick (supplied by the tick producer; today only the Rust fixtures)' and add warm-path transport to Non-goals."
    },
    {
      "id": "SPEC-R1-F05",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L28-L30",
      "evidence": "The strict-decoding requirement names only PolicyEnvelope, PodAllocation, and AssetOverride and does not state that MarketEvent and OnChainTokenSafety stay tolerant, so an implementer could over-apply deny_unknown_fields and break forward-compatible event ingestion.",
      "required_fix": "Add one sentence or Non-goal stating that MarketEvent and OnChainTokenSafety keep serde's default tolerant behaviour and MUST NOT receive deny_unknown_fields."
    },
    {
      "id": "SPEC-R1-F06",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L5; #L48-L61",
      "evidence": "The spec never states that catalyst_score, bias, and max_leverage remain required and non-Option, and no scenario asserts that omitting one fails decoding; the CLI missing-key scenario is generic.",
      "required_fix": "State that the three existing fields stay required (non-Option), and add a scenario where an AssetOverride JSON omits catalyst_score and decoding fails."
    },
    {
      "id": "SPEC-R1-F07",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L14-L16",
      "evidence": "The scenario says a Python envelope omits entry_obi_threshold, but Python's AssetOverride.to_dict() uses asdict and always emits all eleven keys (backend/core/schemas.py#L34-L35); only hand-written or older-producer JSON can omit it.",
      "required_fix": "Reword to 'an envelope JSON omits ...' and state that this tolerates non-Python or older producers."
    },
    {
      "id": "SPEC-R1-F08",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L57,L61; backend/tests/test_architecture.py#L38-L54",
      "evidence": "Impact says trade counts 'may change' but does not name the assertions total_trades == 6, rejected_orders == 1, and total_trades == 4, which fail if the new gates change momentum entries.",
      "required_fix": "Add the Python bridge test and its exact counts to Impact, and require re-baselining with evidence or preservation by deliberate fixture choice."
    },
    {
      "id": "SPEC-R1-F09",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L97-L120",
      "evidence": "Boundary semantics are declared (>= support/resistance, >/< invalidation) but no scenario covers mid == support, mid == resistance, short mid == invalidation, |OBI| == threshold, or rsi_14 == min_rsi_short.",
      "required_fix": "Add the missing boundary scenarios or one table-driven boundary scenario so every inclusive/strict convention is pinned."
    },
    {
      "id": "SPEC-R1-F10",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L46-L53",
      "evidence": "Issue #10's pod_solana_alpha/pod_onchain_alpha canonicalisation drift (backend/core/schemas.py#L67; Rust PodId alias cannot apply to HashMap<String, PodAllocation> keys) is neither in the #10.1-#10.5 scope nor in Non-goals.",
      "required_fix": "Add pod-key canonicalisation to Non-goals as a follow-up issue/ADR, or bring it into scope explicitly."
    },
    {
      "id": "SPEC-R1-F11",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L55-L62",
      "evidence": "Impact omits AGENTS.md and README.md, which state the contract the issue quotes, and omits backend/core/state_store.py and backend/agents/orchestrator.py if F04 is fixed by wiring the warm-path transport.",
      "required_fix": "List the documentation files to update or add them to Non-goals; add the producer files if F04 is resolved by wiring the transport."
    },
    {
      "id": "SPEC-R1-F12",
      "severity": "nit",
      "origin": "initial",
      "status": "open",
      "location": "proposal.md#L5; #L9",
      "evidence": "The outcome says the rules 'gate momentum entries', but TP/SL are only written into the intent (enforcement is #4 and a Non-goal at L49); 'Effort: M' collides with the M/S/L lane vocabulary although this change is lane L.",
      "required_fix": "Reword to 'gate momentum entries and populate TP/SL distances' and write 'Medium' or an estimate instead of 'M'."
    },
    {
      "id": "SPEC-R1-F13",
      "severity": "minor",
      "origin": "initial",
      "status": "open",
      "location": "openspec/changes/align-asset-override-contract/specs/contract/spec.md#L85; backend/core/state_store.py#L461-L464",
      "evidence": "The spec makes min_rsi_short the short RSI guard, while the warm-path paper execution model uses 100.0 - max_rsi_long as the short RSI threshold, giving the same override two short-RSI semantics.",
      "required_fix": "State which semantics is authoritative and require the warm-path evaluation to use min_rsi_short, or document the divergence as intentional."
    }
  ],
  "closed": []
}
```
