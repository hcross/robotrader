# Merge Dossier — fix-leaf-fleet-parity-honesty

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
| SPEC | APPROVE (round 2) | `.sdlc/fix-leaf-fleet-parity-honesty/reviews/spec-r2.md` @ `5385cc30ad05073bead3673899677bd258fb4a77` |
| PLAN | APPROVE (round 1) | `.sdlc/fix-leaf-fleet-parity-honesty/reviews/plan-r1.md` @ `03a22fbd52d1353a80134533d95b94e3f074ee03` |
| DEV | APPROVE (round 1) | `.sdlc/fix-leaf-fleet-parity-honesty/reviews/dev-r1.md` @ `abdf1431ca5504cf8dcc736f9e5a5b6b9a90f8f8` |
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
