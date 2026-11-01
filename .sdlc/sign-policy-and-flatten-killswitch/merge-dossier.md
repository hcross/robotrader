# Merge Dossier — sign-policy-and-flatten-killswitch

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
| SPEC | APPROVE (round 2) | `.sdlc/sign-policy-and-flatten-killswitch/reviews/spec-r2.md` @ `eb6346ccda3ab5024be7e6a2db79ebb8fdee4e1f` |
| PLAN | APPROVE (round 1) | `.sdlc/sign-policy-and-flatten-killswitch/reviews/plan-r1.md` @ `5d5d3c11836fe2ec359ee73691cb7e4dfc0a8b21` |
| DEV | APPROVE (round 1) | `.sdlc/sign-policy-and-flatten-killswitch/reviews/dev-r1.md` @ `d680cebce41c5a250ae7e37aa64e04aa288023be` |
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
