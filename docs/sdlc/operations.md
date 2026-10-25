# Operations — issue, worktree, PR, CI, merge

> Normative contract: `sdlc/PROTOCOL.md` §10–§13.
> Commands: `scripts/sdlc/sdlc.sh`, `scripts/sdlc/run-agent.sh`.

## 1. Prerequisites

| Tool | Why | Check |
|---|---|---|
| `git` | branches, worktrees, SHA pinning | `git --version` |
| `gh` | issue logbook, PR, checks | `gh auth status` |
| `openspec` | spec scaffold and strict validation | `openspec --version` |
| `python3` | driver and linters | `python3 --version` |
| `claude` and/or `agy` | agent execution | `claude --version`, `agy --version` |

Authenticate the forge once, with its own CLI:

```bash
gh auth login
scripts/sdlc/sdlc.sh doctor     # verifies tools, auth, config, adapters, CI
```

The SDLC uses `gh` only. No forge token is stored in the repository.

## 2. First-time repository setup

### 2.1 Labels

### 2.1 Commit the scaffold first

A worktree is created from the base branch. It needs `openspec/config.yaml`,
`sdlc/`, `scripts/sdlc/`, and the generated adapters on that branch. Commit and
push this scaffold to `master` before starting the first change.

### 2.2 Labels

`start` creates the labels it needs when it creates an issue. To create them
up front:

```bash
gh label create sdlc --color 5319E7 --description "Robotrader SDLC" || true
for lane in m:0E8A16 s:FBCA04 l:D93F0B; do
  name="${lane%%:*}"; color="${lane##*:}"
  gh label create "sdlc:lane-$name" --color "$color" --description "SDLC lane $name" || true
done
for stage in triage spec plan dev review merge-ready blocked escalated; do
  gh label create "sdlc:stage-$stage" --color 1D76DB --description "SDLC stage $stage" || true
done
gh label create sdlc:escalated --color B60205 --description "Needs a human decision" || true
```

### 2.3 Branch protection (recommended, admin only)

```bash
gh api -X PUT repos/:owner/:repo/branches/master/protection --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["sdlc", "rust", "python", "frontend"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
JSON
```

Agents never push to `master`. The human merge is the only path.

## 3. Issue logbook

One issue per change. The body starts with a hidden state block, then the human
summary, artifacts, stage ledger, and evidence.

```markdown
<!-- sdlc:state
change_id: add-health-endpoint
lane: S
stage: spec-review
round: 1
branch: sdlc/42-add-health-endpoint
worktree: .worktrees/42-add-health-endpoint
pr:
-->
```

Every transition appends a comment ending with a hidden event marker:

```markdown
<!-- sdlc:event {"ts":"2026-10-25T12:00:00Z","stage":"spec","round":1,"actor":"sdlc-spec-reviewer","verdict":"CHANGES_REQUESTED"} -->
```

- The issue is **append-only**: corrections are new comments.
- The issue is the canonical **status**; `.sdlc/<id>/state.json` is the machine
  cache.
- A cold agent reconstructs status from the issue plus the ledger.

## 4. Worktree lifecycle

```bash
# create (done by sdlc.sh start)
git worktree add -b sdlc/42-add-health-endpoint \
  .worktrees/42-add-health-endpoint master

# work
cd .worktrees/42-add-health-endpoint
scripts/sdlc/sdlc.sh next add-health-endpoint

# close (after merge or abandonment)
scripts/sdlc/sdlc.sh close add-health-endpoint --merged
```

Rules:

- One change per worktree.
- `.worktrees/` is gitignored.
- Do not run two changes touching the same area concurrently.
- `close` copies the ledger to the main checkout before removing the worktree.

## 5. PR lifecycle

| Lane | PR opened | Content |
|---|---|---|
| M | with the fix | fix + evidence |
| S | when DEV starts | approved spec + tasks + code |
| L | when DEV starts | approved spec + design + tasks + code |

- Draft until the dev verdict is `APPROVE`.
- Title: `[<change-id>] <imperative summary>`.
- Body: `sdlc/templates/pr-body.md`, including the Review Card.
- Commits: Conventional Commits with `[<change-id>]`; one commit per correction
  round.
- The PR head SHA is what the dev reviewer reviews. Rebase after the verdict
  invalidates it; request a new round instead of force-pushing silently.
- Link the PR to the change so the merge gate can verify CI and the head SHA:

```bash
scripts/sdlc/sdlc.sh pr <change-id>              # auto-detect by branch
scripts/sdlc/sdlc.sh pr <change-id> --number 43
```

## 6. CI

Two workflows:

| Workflow | Triggers | Jobs |
|---|---|---|
| `sdlc-checks.yml` | `openspec/**`, `sdlc/**`, `docs/sdlc/**`, `scripts/sdlc/**`, `.github/**` | OpenSpec strict, `spec-lint`, `verdict-lint`, adapter drift |
| `ci.yml` | `engine-rs/**`, `backend/**`, `frontend/**` | `cargo test`, Python tests, frontend build |

CI is a gate, not a reviewer. A green CI does not replace a dev verdict.

## 7. Merge gate

```bash
scripts/sdlc/sdlc.sh merge-ready add-health-endpoint
```

Requires:

- every required stage `APPROVE` at the current SHA;
- zero open blocker/major;
- `openspec validate --strict`, `spec-lint`, `verdict-lint` pass;
- tasks checked (or explicitly waived);
- PR checks green.

Then:

1. Dispatch `sdlc-merge-verifier` to build the dossier independently.
2. Invoke the `user-validate` skill with the dossier. The human chooses merge,
   merge with follow-up, request changes, or abandon.
3. The human merges. If an agent merges, it needs explicit written delegation
   recorded in the issue.

### 7.1 Full-auto merge

```bash
scripts/sdlc/sdlc.sh merge <change-id> --delegated-by "<operator / reference>"
```

The command re-runs `merge-ready`, then refuses unless:

- every required verdict is `APPROVE` at the PR head;
- no open blocker/major exists;
- CI checks are green;
- the PR is ready and mergeable;
- no escalation is recorded.

It records the delegation in `state.json` and on the PR, merges, pulls the base
branch, archives the OpenSpec change, commits the ledger, closes the issue, and
removes the worktree. A safety/security escalation still stops the merge.

## 8. Escalation playbook

| Trigger | Human sees | Default recommendation |
|---|---|---|
| `rounds-exhausted` | open findings, two options | split the change or accept a documented risk |
| `scope-change` | new scope vs original spec | new change, not a bigger PR |
| `safety-ambiguity` | money/risk/vault question | do not merge until decided |
| `lane-downgrade` | safeguards removed | keep the higher lane |
| `ci-red` | failing checks after 2 fixes | stop and diagnose |
| `irreversible` | migration or destructive step | require a rollback plan |

An escalation dossier contains the trigger, evidence, 2–3 options with cost and
risk, and a recommendation. The agent stops; it does not choose the risky path.

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `gh: not logged in` | no forge auth | `gh auth login` |
| `no OpenSpec changes directory` | OpenSpec not initialized | `openspec init --tools none .` |
| `change already has state` | retry after partial start | inspect `.sdlc/<id>/state.json`; close or remove deliberately |
| worktree path exists | previous run | `git worktree list`, then remove or reuse |
| `worktree is dirty` | unrelated edits | commit or stash before the next stage |
| `round 3 must ESCALATE` | reviewer requested changes at the cap | escalate, do not edit the verdict |
| `new finding ... must be regression/security/critical` | moving goalposts | move it to a follow-up issue |
| `openspec validate` fails | malformed delta | fix the exact issue OpenSpec reports |
| Antigravity: `unknown agent` | adapter missing | `scripts/sdlc/install-agents.sh` |
| Claude: nested session refused | `CLAUDECODE` set | `SDLC_CLI=agy` or `SDLC_ALLOW_NESTED_CLAUDE=1` |
| `gh pr checks` pending | CI still running | wait; do not bypass the gate |

## 10. Concurrency and locking

- `SDLC_MAX_PARALLEL` default 3.
- One active change per `sdlc:area-*`.
- State writes use an advisory file lock; `state.json` is written atomically.
- Two changes touching the same crate or contract must be serialized, even in
  different worktrees.

## 11. Security hygiene

- No secret, key, `.env`, or production address in specs, verdicts, evidence,
  briefs, or dossiers.
- Vault/key changes are Lane L by definition.
- Evidence commands must not print environment variables or credentials.
- The reviewer checks for leaked secrets as a blocker.

## 12. Metrics worth tracking

| Metric | Source | Healthy direction |
|---|---|---|
| Review rounds per stage | `state.json` | 1–2, rarely 3 |
| Escalation rate | issue label `sdlc:escalated` | low, and each one actionable |
| Review Card read time | `spec-lint` info | < 3 min |
| Lead time by lane | issue created → merged | stable or falling |
| Escaped defects | post-merge issues linked to a change | zero for blockers |

Review the metrics monthly. If a lane consistently needs three rounds, the
problem is usually the spec, not the reviewer.
