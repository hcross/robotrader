# feed-panorama-provenance Specification

## Purpose
TBD - created by archiving change fix-leaf-fleet-parity-honesty. Update Purpose after archive.
## Requirements
### Requirement: Social/macro panorama composite sentiment casing

`SocialMacroPanoramaTool.build_panorama` (`backend/tools/ta_tools.py`) MUST return the composite sentiment under the key `"composite_sentiment"` (lowercase `c`). To ensure backward compatibility with any external or legacy caller, it MAY also retain `"Composite_sentiment"` as a duplicate alias. `OrchestratorAgent._build_reflection_prompts` (`backend/agents/orchestrator.py`) MUST successfully receive a non-null float or string representation for `composite_sentiment` from the panorama payload, eliminating the defect where sentiment was silently dropped as `null`.

#### Scenario: Panorama returns lowercase composite sentiment
- **WHEN** `SocialMacroPanoramaTool.build_panorama` is invoked with valid TA snapshots
- **THEN** the returned dictionary contains the key `"composite_sentiment"`
- **THEN** the value associated with `"composite_sentiment"` is a valid numeric sentiment score

#### Scenario: Orchestrator reflection prompt receives non-null composite sentiment
- **WHEN** `OrchestratorAgent._build_reflection_prompts` builds prompts using a generated panorama
- **THEN** `pano_compact["composite_sentiment"]` is not `null`
- **THEN** the synthesized prompt text contains the numeric sentiment value

#### Scenario: Legacy uppercase key remains available for backward compatibility
- **WHEN** an external caller reads `panorama["Composite_sentiment"]`
- **THEN** the key exists and equals the value of `panorama["composite_sentiment"]`

### Requirement: Dynamic confluence calculation over present symbol snapshots

In `SocialMacroPanoramaTool.build_panorama`, the multi-timeframe confluence score MUST be computed as the arithmetic mean of the `confluence_score` values across only the symbols actually present in `ta_snapshots`. The computation MUST NOT assume hardcoded keys `BTC/USDT` and `ETH/USDT` when those keys are absent from the snapshot dictionary, and MUST NOT divide by an arbitrary fixed denominator (such as `3.0`) when fewer symbols are present. When `ta_snapshots` contains no symbols or no symbol has a valid `confluence_score`, the score MUST fall back to a neutral default of `0.0`.

#### Scenario: Confluence calculated from available Solana symbols
- **WHEN** `ta_snapshots` contains snapshots for `SOL/USDT`, `JUP/USDT`, and `RAY/USDT`, with no `BTC/USDT` or `ETH/USDT`
- **THEN** the average confluence score equals the sum of the three present scores divided by 3
- **THEN** absent symbols do not inject zero-value skew into the denominator

#### Scenario: Single-symbol snapshot computes exact single score
- **WHEN** `ta_snapshots` contains only `SOL/USDT` with `confluence_score = 0.60`
- **THEN** the average confluence score equals `0.60`
- **THEN** it does not equal `0.20`

#### Scenario: Empty snapshot yields neutral fallback
- **WHEN** `ta_snapshots` is an empty dictionary
- **THEN** the average confluence score defaults to `0.0`
- **THEN** `composite_sentiment` evaluates to its neutral baseline without raising a `ZeroDivisionError`

### Requirement: Static social and macro narrative fields declare synthetic provenance

In `SocialMacroPanoramaTool.build_panorama`, all static narrative fields and signal dictionaries — including items in `social_signals` (such as `crypto_twitter_narrative`, `macro_regime`, `whale_onchain_flow`, `funding_and_oi_regime`) — MUST carry explicit provenance metadata: `source_kind: "SYNTHETIC_FIXTURE"`. Static narrative text MUST NOT be returned without this metadata, ensuring that deterministic template text is never misrepresented to the LLM or operator as live social media telemetry.

#### Scenario: Social signals declare synthetic fixture provenance
- **WHEN** `SocialMacroPanoramaTool.build_panorama` returns `social_signals`
- **THEN** every signal item contains `source_kind: "SYNTHETIC_FIXTURE"`
- **THEN** no signal item claims live social platform ingestion

#### Scenario: Panorama root payload declares narrative provenance
- **WHEN** the panorama payload is inspected
- **THEN** its narrative components declare `source_kind: "SYNTHETIC_FIXTURE"`
- **THEN** `urgency_level` remains computed from available technical indicators

### Requirement: Ecosystem RSS feed provenance stamping

`EcosystemRSSAggregator.get_feed_for_agent` (`backend/tools/rss_tools.py`) MUST stamp every item in `items` with machine-readable provenance:
- When an item is successfully fetched from an external live XML/Atom feed, it MUST carry `source_kind: "LIVE_RSS"` and `curated: false`.
- When an item is served from `CURATED_ECOSYSTEM_ITEMS` or fallback catalog entries, it MUST carry `source_kind: "CURATED_FIXTURE"` and `curated: true`.
Static curated items MUST NOT be stamped with synthetic fresh timestamps that mimic real-time breaking news; their timestamp MUST be a fixed fixture timestamp or clearly identified as a fixture reference.
The returned feed dictionary MUST include a feed-level provenance summary containing:
- `feed_mode`: `"LIVE"` if all items are live (`live_count > 0` and `curated_count == 0`), `"MIXED"` if both exist (`live_count > 0` and `curated_count > 0`), or `"CURATED_FALLBACK"` if all items are curated or if `items` is empty (`live_count == 0`).
- `live_count`: integer count of live items.
- `curated_count`: integer count of curated items.

#### Scenario: Curated fallback items declare curated fixture provenance
- **WHEN** `get_feed_for_agent` is called with `try_network=False` or when network fetch fails
- **THEN** every returned item carries `source_kind: "CURATED_FIXTURE"` and `curated: true`
- **THEN** the feed summary reports `feed_mode: "CURATED_FALLBACK"`, `live_count: 0`, and `curated_count > 0`

#### Scenario: Live RSS items declare live RSS provenance
- **WHEN** `get_feed_for_agent` successfully fetches items from an active network XML feed
- **THEN** each fetched item carries `source_kind: "LIVE_RSS"` and `curated: false`
- **THEN** the feed summary reports `feed_mode: "LIVE"` and `live_count > 0`

#### Scenario: Curated items do not fabricate real-time fresh timestamps
- **WHEN** `get_feed_for_agent` returns curated items on successive invocations
- **THEN** the items carry consistent fixture timestamps or fixture reference markers
- **THEN** timestamps are not artificially recalculated as `now_ms - idx * 420_000` to simulate recent publication

#### Scenario: Empty feed items collection defaults to curated fallback mode
- **WHEN** `get_feed_for_agent` produces an empty item collection where both `live_count` and `curated_count` equal 0
- **THEN** `feed_mode` equals `"CURATED_FALLBACK"`
- **THEN** `live_count` is 0 and `curated_count` is 0

