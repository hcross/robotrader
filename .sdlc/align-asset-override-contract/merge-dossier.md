# Merge Dossier — align-asset-override-contract

## Decision Card (≤ 5 min)

| Field | Value |
|---|---|
| What ships | One line. |
| Why | One line. |
| Blast radius | Services, crates, contracts, chains. |
| Worst failure | One line + detection. |
| Rollback | One command or one step. |
| Risk | Low / Medium / High. |
| Recommendation | Merge / Merge with follow-up / Do not merge. |

```mermaid
flowchart LR
  A["Before"] --> B["After"] --> C["Verified by"]
```

## Evidence

| Gate | Result | Evidence |
|---|---|---|
| SPEC | APPROVE (round 2) | `.sdlc/align-asset-override-contract/reviews/spec-r2.md` @ `5bc41cddcf0ec84c9901bfe89cf68e959fc786b9` |
| PLAN | APPROVE (round 2) | `.sdlc/align-asset-override-contract/reviews/plan-r2.md` @ `7e6ee05715aaf898f62bce8f1dfd3abbc92a032a` |
| DEV | APPROVE (round 2) | `.sdlc/align-asset-override-contract/reviews/dev-r2.md` @ `ab814e31fa5f9252987d01b740cafbcea1bda598` |
| CI | green | `gh pr checks` output |
| Tests | pass | command + summary |
| Lints | pass | command + summary |

## Diff

- Files: <n> · +<add> / -<del>
- Areas: <crates/services>
- New dependencies: <none | list + rationale>

## Residual risk and follow-ups

- <none | item + issue link>

## Human decision

- [ ] Merge
- [ ] Merge with follow-up
- [ ] Request changes
- [ ] Abandon
