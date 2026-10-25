# Merge Dossier — harden-build-packaging

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
| SPEC | APPROVE (round 2) | `.sdlc/harden-build-packaging/reviews/spec-r2.md` @ `2a7f0350c6915cbbff25dc2ec1620d5993ec2170` |
| PLAN | APPROVE (round 2) | `.sdlc/harden-build-packaging/reviews/plan-r2.md` @ `2f57e0f0d346b120e1aabec13fbdaa81f986a9fd` |
| DEV | APPROVE (round 2) | `.sdlc/harden-build-packaging/reviews/dev-r2.md` @ `7e5fd0512aab91925fbd9e16a128380a4618a20c` |
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
