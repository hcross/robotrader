# Merge Dossier — mark-vault-simulated

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
| SPEC | APPROVE (round 2) | `.sdlc/mark-vault-simulated/reviews/spec-r2.md` @ `65ae70510af46b7a29f2ee6abb097a875ea58777` |
| PLAN | APPROVE (round 2) | `.sdlc/mark-vault-simulated/reviews/plan-r2.md` @ `45f6b1e34061f28d0ce4a6742b530126401f0fd6` |
| DEV | APPROVE (round 1) | `.sdlc/mark-vault-simulated/reviews/dev-r1.md` @ `76b6d098431f74094dc68705b4cdbb505b9054cb` |
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
