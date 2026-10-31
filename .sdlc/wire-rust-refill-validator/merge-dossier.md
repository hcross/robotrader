# Merge Dossier — wire-rust-refill-validator

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
| SPEC | APPROVE (round 1) | `.sdlc/wire-rust-refill-validator/reviews/spec-r1.md` @ `b367ae64125c40658913de9c9cf406ab3fa69ce9` |
| PLAN | APPROVE (round 1) | `.sdlc/wire-rust-refill-validator/reviews/plan-r1.md` @ `e14fc090db5dce83de7aab73a9685b804b7aa3f9` |
| DEV | APPROVE (round 1) | `.sdlc/wire-rust-refill-validator/reviews/dev-r1.md` @ `52659aaa3fe46b1e48ad94f2db8d6eb3e908a493` |
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
