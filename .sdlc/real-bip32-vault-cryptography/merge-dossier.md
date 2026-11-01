# Merge Dossier — real-bip32-vault-cryptography

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
| SPEC | APPROVE (round 2) | `.sdlc/real-bip32-vault-cryptography/reviews/spec-r2.md` @ `14382f5a348039afaf4c644e4e8094905c3311c0` |
| PLAN | APPROVE (round 1) | `.sdlc/real-bip32-vault-cryptography/reviews/plan-r1.md` @ `f7523c317c5ae136da94422a1fe782af7d7a22ef` |
| DEV | APPROVE (round 1) | `.sdlc/real-bip32-vault-cryptography/reviews/dev-r1.md` @ `ef10000b06f3e0b745faa877f274a99f0e4804c2` |
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
