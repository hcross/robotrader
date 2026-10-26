# Merge Dossier — fix-costguard-python-gate

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
| SPEC | APPROVE (round 2) | `.sdlc/fix-costguard-python-gate/reviews/spec-r2.md` @ `1ef4c638295fbc8e3fc24601d68b7c1250c2e735` |
| PLAN | APPROVE (round 2) | `.sdlc/fix-costguard-python-gate/reviews/plan-r2.md` @ `ad721ce260e568f64fbc5a95002ad2148106cfe7` |
| DEV | APPROVE (round 1) | `.sdlc/fix-costguard-python-gate/reviews/dev-r1.md` @ `ea4f3a9760ecc15cdef8143a73d5ebcec01a9517` |
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
