# [SDLC] <change-id> — <title>

<!-- sdlc:state
change_id: <change-id>
lane: <M|S|L>
lane_reason: "<one line>"
stage: triage
round: 0
branch: sdlc/<issue>-<slug>
worktree: .worktrees/<issue>-<slug>
pr:
base_branch: master
-->

## Outcome

<One line: what is true after this change that is not true now.>

## Why now

<Observed problem or opportunity. Facts, not preferences.>

## Lane

**<M|S|L>** — <one-line justification against the rubric in `sdlc/PROTOCOL.md` §2.1.>

## Artifacts

| Artifact | Path | Status |
|---|---|---|
| SPEC | `openspec/changes/<change-id>/proposal.md` | pending |
| Delta specs | `openspec/changes/<change-id>/specs/**` | pending |
| PLAN | `openspec/changes/<change-id>/design.md` | N/A for this lane |
| Tasks | `openspec/changes/<change-id>/tasks.md` | pending |
| PR | — | pending |

## Stage ledger

| Stage | Round | Reviewer | Verdict | SHA | At |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## Review ledger

| Finding | Severity | Status | Round closed | Evidence |
|---|---|---|---|---|
| — | — | — | — | — |

## Decisions

- <Decision + rationale + ADR link if any.>

## Escalations

- <none>

## Evidence

- <command → result, or link to `.sdlc/<change-id>/evidence/...`>

---

<!-- Append-only. Corrections are new comments, never silent edits of history. -->
<!-- sdlc:event {"ts":"<iso8601>","stage":"triage","round":0,"actor":"sdlc-conductor","verdict":null} -->
