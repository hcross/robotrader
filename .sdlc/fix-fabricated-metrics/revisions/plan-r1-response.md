stage: plan
round: 1
head_sha: e81e2a5efb7800ff641058cc8756ae3336f4a933
responses:
  - id: PLAN-R1-F01
    action: fixed
    evidence: "Added D17 and a 'D5/D17 — testnet_telemetry contract' section to design.md: `simulated_model_pnl_usd` and `solana_onchain_pnl_sol` are removed, and the block keeps only measured testnet wallet/order telemetry with one `MEASURED` source. tasks.md 1.7 implements the removal; the Verification curl asserts both keys are absent and `source == 'MEASURED'`; the grep gates include both field names."
  - id: PLAN-R1-F02
    action: fixed
    evidence: "tasks.md 2.4 now emits `contract_version: 2` in `get_system_status`; tasks.md 8.7 records the `BREAKING CHANGE:` PR footer and the issue-logbook note. design.md traceability now has a 'Breaking API communication and version marker' row mapping D14 to tasks 2.4 and 8.7. The Verification curl asserts `contract_version == 2`."
  - id: PLAN-R1-F03
    action: fixed
    evidence: "design.md D8/D9/D10 now enumerates all four real-call sites by function and line: `run_strategic_reflection` strategy_ledger (~L479), its leaf_solana mirror (~L501), `run_master_orchestrator_reflection` (~L743), and `run_leaf_agent_reflection` (~L910). tasks.md 4.5 labels each as `LLM` or `DETERMINISTIC_FALLBACK` from `parsed_from_llm` and makes the mirror inherit the parent. tasks.md 4.8 adds a test that a successful strategic reflection writes `source == 'LLM'` in `strategy_ledger`."
  - id: PLAN-R1-F04
    action: fixed
    evidence: "The Verification gate is now `git grep -n 'rust_leaf_backtest' -- backend/core backend/agents backend/server.py`, with the text stating that `backend/tests/` is excluded deliberately because the rejection test in tasks.md 1.2 contains the token. design.md D4 carries the same production-only scope."
  - id: PLAN-R1-F05
    action: fixed
    evidence: "design.md D2 now has a 'Window basis (disclosed)' paragraph: the leaf and treasury use the recent 200-row window, `engine_metrics.live_testnet.cumulative_cex_pnl_usd` stays lifetime, the basis is named in `source_detail`, and the alternative would require a spec-gap. The live `source_detail` string includes 'recent 200-row window', the Risk list records the divergence, and tasks.md 2.11 adds the >200-row eviction test."
  - id: PLAN-R1-F06
    action: fixed
    evidence: "design.md now has a 'D7 — Redis compaction payload' section defining `_persisted_payload()` as the complete payload (capital, thesis, leaves with only the five allowed keys, deposit and checkout histories). tasks.md 3.2 builds that full payload for both `persist()` and the compaction; tasks.md 3.3 asserts `total_capital_usd`, `long_term_strategy_thesis`, `deposit_history`, and `checkout_history` survive."
  - id: PLAN-R1-F07
    action: fixed
    evidence: "tasks.md 1.5 now labels both branches: `run_rust_backtest` sets `source = FIXTURE`, so the `leaf-solana` early return is already labelled, and the non-Solana branch adds the leaf-replay detail. tasks.md 1.10 adds a test for `run_rust_backtest_for_leaf('leaf-solana')` and `POST /api/v1/leaf/leaf-solana/backtest`."
  - id: PLAN-R1-F08
    action: fixed
    evidence: "design.md D12 and the 'D12/D13 — Rendering contract' section now define two functions: `formatMetric(value, source, kind)` for performance values and `formatOperational(value, kind)` for capital, credit, allocation, and counts. Operational values render `—` for null and `$0.00` for measured zero, with no badge; the source-label clause is read as applying to performance blocks. tasks.md 6.1, 6.4, and 6.8 implement and assert both; the Risk list records the interpretation."
  - id: PLAN-R1-F09
    action: fixed
    evidence: "tasks.md 6.4/6.5/6.6 enumerate every spec-listed surface (leaf PnL/Sharpe/win-rate tile, Rust panel metrics, execution rows, Master leaf-table column, Dashboard population/HardRiskGate/testnet tiles, execution PnL columns, drawer lists) and require removal of every `|| 0` / `?? 0` on performance values. tasks.md 6.7 adds `frontend/scripts/check-provenance.mjs`, an executable static assertion that each component imports `provenance.js` and that the forbidden defaults are absent. tasks.md 6.9 enumerates the leaf, Master-table, and Dashboard null-state screenshots."
  - id: PLAN-R1-F10
    action: fixed
    evidence: "tasks.md 2.3 requires every `get_leaf_detail` path (snapshot, `GET /api/v1/leaf/{leaf_id}`, mandate response) to pass `state_store.get_population_metrics()`, with a defensive null-valued path that keeps the population sources. tasks.md 2.10 tests the direct leaf endpoint and the mandate response."
  - id: PLAN-R1-F11
    action: fixed
    evidence: "tasks.md 1.9 creates `backend/tests/test_integrity_provenance.py` with the auditor-source test; task 8.1 names the same file for the recursive payload test. The Verification now captures the test output and requires `Ran [1-9][0-9]* test` and `OK`, so zero discovered tests cannot pass."
  - id: PLAN-R1-F12
    action: fixed
    evidence: "design.md D9 and the D8/D9/D10 section now require both prompt builders to scan the full drawer list by wing and source before applying the limit, never `recall_recent(limit=N)` then filter. tasks.md 4.3 states the same order and adds tasks.md 4.7, which tests an eligible `LLM` drawer behind newer `BOOTSTRAP` drawers."
  - id: PLAN-R1-F13
    action: fixed
    evidence: "tasks.md 2.6 removes the `active_positions_count = 0` assignment from `emergency_liquidate_leaf`; tasks.md 2.8 tests that the post-liquidation leaf carries `null` (or no key) and never `0`."
  - id: PLAN-R1-F14
    action: fixed
    evidence: "tasks.md 6.6 removes the `|| 'backtest_fixture'` default and renders a missing `executions_source` as `UNATTRIBUTED`; tasks.md 6.7's static script rejects `|| 'backtest_fixture'` in the component sources."
  - id: PLAN-R1-F15
    action: fixed
    evidence: "design.md D16 now scopes figure blocks to trading-performance figures (§1 and §3), labels the §2/§4 inference-cost tables as operational cost measurements outside the three populations, and states that new text follows the English-only convention while the pre-existing French body is a recorded legacy exception. tasks.md 7.1 and 7.2 implement the scope and language rule."
  - id: PLAN-R1-F16
    action: fixed
    evidence: "tasks.md 1.3, 1.5, 1.6, 1.7, 1.8, and 4.1 now reference `provenance.METRIC_SOURCES`, `provenance.DRAWER_SOURCES`, `provenance.EXECUTIONS_SOURCE_TO_METRIC_SOURCE`, and `provenance.execution_rows_source()` instead of bare literals. design.md traceability adds rows for D14 (breaking API communication) and D15 (test strategy without a frontend runner)."
  - id: PLAN-R1-F17
    action: fixed
    evidence: "The large test tasks are split: 2.6 -> 2.7, 2.8, 2.9, 2.10, 2.11; 4.6 -> 4.6, 4.7, 4.8; 8.1 is now the single recursive payload test in the named module, with the remaining evidence and rollout work in 8.2–8.8."
