# Merge Dossier — enforce-risk-exposure-caps-and-ratelimit

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
| SPEC | APPROVE (round 2) | `.sdlc/enforce-risk-exposure-caps-and-ratelimit/reviews/spec-r2.md` @ `4ff66d6d9a16723e8d64d63059a9246f09653996` |
| PLAN | APPROVE (round 1) | `.sdlc/enforce-risk-exposure-caps-and-ratelimit/reviews/plan-r1.md` @ `cd3c84a3ae37c3f24224cee2d3f50bb886964f08` |
| DEV | APPROVE (round 1) | `.sdlc/enforce-risk-exposure-caps-and-ratelimit/reviews/dev-r1.md` @ `a06a03d75ce57e02326d6dd6e5f01a1128f08365` |
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
