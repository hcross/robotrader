# Merge Dossier — event-driven-fill-simulator

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
| SPEC | APPROVE (round 1) | `.sdlc/event-driven-fill-simulator/reviews/spec-r1.md` @ `572d61aa39264449372b6c581def29221bba2c78` |
| PLAN | APPROVE (round 1) | `.sdlc/event-driven-fill-simulator/reviews/plan-r1.md` @ `785176c23862002c05928b193313f02d0c4c12b4` |
| DEV | APPROVE (round 1) | `.sdlc/event-driven-fill-simulator/reviews/dev-r1.md` @ `679cff2d95c14860d7e77aba3a8efbafcd81c366` |
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
