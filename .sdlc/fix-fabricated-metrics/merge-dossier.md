# Merge Dossier — fix-fabricated-metrics

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
| SPEC | APPROVE (round 2) | `.sdlc/fix-fabricated-metrics/reviews/spec-r2.md` @ `a17d3a240d7ef85a931157c2fe44227b370e8873` |
| PLAN | APPROVE (round 2) | `.sdlc/fix-fabricated-metrics/reviews/plan-r2.md` @ `fd9eff5609b76affbb4053c7d919500575a92d84` |
| DEV | APPROVE (round 1) | `.sdlc/fix-fabricated-metrics/reviews/dev-r1.md` @ `a9718e4d72a550ab65f5263c65f89d2875648c6a` |
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
