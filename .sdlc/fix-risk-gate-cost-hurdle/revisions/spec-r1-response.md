stage: spec
round: 1
head_sha: 1a2ce17761620d11670d8b633391c7f1b5f5a197
responses:
  - id: SPEC-R1-F01
    action: fixed
    evidence: >-
      Chose option (b): the new requirement "Safety gates precede the edge
      hurdle" fixes the order as kill switch -> drawdown -> effective
      envelope/pod -> slippage ceiling -> token safety -> edge hurdle ->
      leverage clamp -> Kelly/zero-position. Requirement 6 now scopes the
      same-variant invariant to an intent that reaches the gate. Added the
      scenario "The SCAM-SOL fixture is rejected as a rug, not by the hurdle"
      (OnchainDexAggregator, MevBundleAtomic, edge 81.0, max_slippage 65,
      hurdle 87.8, malicious token safety -> OnChainRugCheckFailed) and
      "Excessive slippage below the hurdle still wins" (edge 1.0,
      max_slippage 30 against a 25 cap -> ExcessiveSlippage). The Review Card
      Decision needed now states the precedence choice.
  - id: SPEC-R1-F02
    action: fixed
    evidence: >-
      Added requirement "Fixture baselines are regenerated from a real run"
      with scenarios for unchanged fixture inputs, the re-derived deterministic
      backtest baseline (4 trades, 3 rejections, 2 pods; SCAM-SOL still
      OnChainRugCheckFailed), regenerated [FIXTURE] figures matched to the node
      JSON, and the 26-leaf per-leaf assertions. The requirement names the
      commands `cargo test --manifest-path engine-rs/Cargo.toml -p
      robotrader-backtest` and `cargo run --manifest-path engine-rs/Cargo.toml
      -p robotrader-node -- --leaf-id <leaf>`; PLAN must place both in
      `## Verification`.
  - id: SPEC-R1-F03
    action: fixed
    evidence: >-
      Added the scenario "The spread term matches the executor for all four
      order types" asserting PostOnlyMaker 0.5, Limit 2.0, Market 8.0, and
      MevBundleAtomic 6.0 bps at a tip of 10, identical on the gate side and in
      `SmartExecutionRouter::slippage_bps_for`. The requirement now forbids
      constructing a throwaway `ApprovedOrder` or allocating inside the gate;
      the parity test may construct one.
  - id: SPEC-R1-F04
    action: fixed
    evidence: >-
      The benchmark requirement now names every occurrence of the <50µs claim:
      README.md lines 8, 42, 48, 75; docs/architecture.md line 52; and
      docs/PERFORMANCE_AND_COST_AUDIT.md lines 4, 37, 65, 79, 145. Added the
      scenario "Every <50µs occurrence carries the measured number".
  - id: SPEC-R1-F05
    action: fixed
    evidence: >-
      Requirement 6 adds scenarios for an already-active kill switch
      (KillSwitchActive), zero/negative Kelly sizing (ZeroPositionSize), and
      validate_inference_refill (valid refill accepted, above-watermark refill
      rejected), alongside the existing drawdown, pod-disabled, TTL-fallback,
      and leverage-clamp scenarios.
  - id: SPEC-R1-F06
    action: fixed
    evidence: >-
      Softened the claim to "MUST NOT add" an allocation site and made the
      evidence explicit: a cold dev review of the diff must show no new
      allocation, logging, I/O, sleeping, or unbounded loop, with the
      pre-existing effective-envelope and ApprovedOrder clones grandfathered.
      Added the scenario "The hot-path diff adds no allocating or blocking
      site".
