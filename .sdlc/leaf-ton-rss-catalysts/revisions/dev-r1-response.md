stage: dev
round: 1
head_sha: bb1ecf22e26c52d14e9b54dd5c629b491f6b6ee4
responses:
  - id: DEV-R1-F01
    action: fixed
    evidence: "Reordered the venue branches in EcosystemRSSAggregator.score_ton_catalyst so DeDust-specific terms ('dedust','de dust','dedust.io') are evaluated before the STON.fi/generic DEX terms. DeDust items (e.g. 'DeDust liquidity pool surge', 'DeDust swap growth') now classify as TON_DEDUST_DEX. Verified with direct Python calls and test_ton_rss_atom_parsing_and_catalyst_scoring (PASS)."
