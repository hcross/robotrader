# Merge Dossier — fix-provenance-gate-evidence

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
| SPEC | APPROVE (round 1) | `.sdlc/fix-provenance-gate-evidence/reviews/spec-r1.md` @ `c1a03f9487acf5b50ec6e624b9127ccc6b364f2e` |
| DEV | APPROVE (round 1) | `.sdlc/fix-provenance-gate-evidence/reviews/dev-r1.md` @ `682af1a12a01ab873973585c81b4a2e352728269` |
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
