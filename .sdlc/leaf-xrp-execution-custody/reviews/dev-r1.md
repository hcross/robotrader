# DEV Review — Round 1

## Summary
Reviewed PR #215 at `bd841c2216f4e9adbee7d82b96c48a710c777c11` (base `d189e71`). The change adds `XrpVenueAdapter` (XRP-RLUSD bridge quote, XRPL destination validation), aliases, `leaf-xrp` symbol isolation in `SmartExecutionRouter`, and two tests. It mirrors the established BNB/Hyperliquid pattern and the Rust/Python/unit/CI checks pass. One major validation-boundary defect needs fixing: XRPL destination validation accepts too many inputs relative to the chain's actual 33–34 character classic addresses and Ripple base58 alphabet.

## Findings

### DEV-R1-F01 — [major] XRPL destination validation is too permissive
- Location: `engine-rs/crates/exec-router/src/lib.rs:458` (`XrpVenueAdapter::validate_settlement_destination`)
- Evidence: the function accepts any string starting with `bridge:` with at least one extra byte (`dest.len() > prefix_len`), and any `r`-prefixed string whose remainder is 24..=34 ASCII alphanumeric characters. The chain's own validator in `engine-rs/crates/risk-gate/src/crypto_vault.rs` requires an XRPL classic address to be 33–34 characters total (32–33 bytes after `r`) and to be Ripple base58check with version byte `0x00`; the exec-router predicate therefore accepts lengths (25–32 or >34) and characters (`0`, `O`, `I`, `l`) that the vault rejects. Concrete examples accepted today but rejected by the vault path include `r` + 24 ASCII chars and `r...0...`.
- Required fix: make the exec-router predicate mirror the chain format used elsewhere: accept only `bridge:xrpl:` / `bridge:ripple:` destinations with a non-empty suffix, or an `r`-prefixed string that is 33–34 total characters (32–33 after `r`) whose remainder uses the Ripple base58 alphabet (`123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz`).
- Status: open
- Origin: initial

## Checks run
- `cd engine-rs && cargo test` → PASS (all suites; exec-router 59 tests + isolation tests included)
- `PYTHONPATH=. python3 -m unittest discover -s backend/tests -v` (Python 3.11, deps installed) → PASS (306 tests, OK)
- `cd frontend && npm run build` (run in `/Users/hoanicross/devel/perso/cryptocurrency/robotrader/frontend`, PR touches no frontend files) → PASS
- `gh pr checks 215` → frontend pass, helm pass, python pass, rust pass
- `git diff --stat d189e71...bd841c2` → only added `XrpVenueAdapter`/aliases, `leaf-xrp` isolation, and tests plus `.sdlc` artifacts

## Machine Verdict

```json
{
  "schema": "sdlc.verdict/v1",
  "change_id": "leaf-xrp-execution-custody",
  "stage": "dev",
  "round": 1,
  "reviewer": "sdlc-dev-reviewer",
  "reviewed_sha": "bd841c2216f4e9adbee7d82b96c48a710c777c11",
  "verdict": "CHANGES_REQUESTED",
  "summary": "XrpVenueAdapter and leaf-xrp isolation match the established pattern and all CI checks pass, but XRPL destination validation is too permissive versus the chain's own 33-34 character Ripple base58-check format and must be tightened.",
  "findings": [
    {
      "id": "DEV-R1-F01",
      "severity": "major",
      "origin": "initial",
      "status": "open",
      "location": "engine-rs/crates/exec-router/src/lib.rs:458",
      "evidence": "validate_settlement_destination accepts r-prefixed strings with 24..34 ASCII alphanumeric bytes and any bridge: suffix; crypto_vault.rs requires 33-34 total XRPL classic address chars and Ripple base58check version 0x00.",
      "required_fix": "Require bridge:xrpl:/bridge:ripple: prefixes only and XRPL r-addresses of 33-34 total chars using the Ripple base58 alphabet."
    }
  ],
  "closed": []
}
```
