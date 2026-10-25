#!/usr/bin/env python3
"""Robotrader SDLC driver.

Deterministic state transitions around the agentic SPEC -> PLAN -> DEV loop.
The agents do the thinking; this tool enforces lanes, rounds, gates, and the
issue/worktree/branch/PR contract.

Run `scripts/sdlc/sdlc.sh help` for usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

LANE_STAGE_ORDER = {
    "M": ("dev",),
    "S": ("spec", "dev"),
    "L": ("spec", "plan", "dev"),
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def replace_template(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def issue_state_block(state: dict, stage: str | None = None, round_no: int | None = None) -> str:
    lines = [
        "<!-- sdlc:state",
        f"change_id: {state['change_id']}",
        f"lane: {state['lane']}",
        f"stage: {stage or state['status']}",
        f"round: {round_no if round_no is not None else max((s['rounds'] for s in state['stages'].values()), default=0)}",
        f"branch: {state['branch']}",
        f"worktree: {state['worktree']}",
        f"pr: {state['pr'] if state['pr'] is not None else ''}",
        "-->",
    ]
    return "\n".join(lines)


def append_event(state: dict, *, stage: str, round_no: int, actor: str, verdict: str | None, summary: str) -> None:
    event = {
        "ts": common.now_iso(),
        "stage": stage,
        "round": round_no,
        "actor": actor,
        "verdict": verdict,
        "sha": state.get("stages", {}).get(stage, {}).get("last_sha"),
    }
    body = (
        issue_state_block(state, stage=state["status"], round_no=round_no)
        + "\n\n"
        + summary
        + "\n\n"
        + common.event_marker(event)
    )
    common.issue_comment(int(state.get("issue", 0)), body)


def stage_status_label(state: dict) -> str:
    return state["status"]


def advance_after_approval(state: dict, stage: str) -> None:
    order = LANE_STAGE_ORDER[state["lane"]]
    index = order.index(stage)
    if index + 1 < len(order):
        next_stage = order[index + 1]
        state["stages"][next_stage]["status"] = "pending"
        state["status"] = next_stage
    else:
        state["status"] = "merge-ready"


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_start(args: argparse.Namespace) -> int:
    cfg = common.load_config()
    change_id = args.change
    common.validate_change_id(change_id)

    if common.state_path(change_id).exists():
        common.die(f"change {change_id!r} already has state at {common.state_path(change_id)}")

    lane = args.lane.upper()
    if lane not in LANE_STAGE_ORDER:
        common.die("--lane must be M, S, or L")
    base_branch = args.base_branch or cfg["SDLC_BASE_BRANCH"]
    areas = [item.strip() for item in (args.areas or "").split(",") if item.strip()]
    human_gates = [item.strip() for item in (args.human_gates or cfg["SDLC_HUMAN_GATES"]).split(",") if item.strip()]

    # 1. Issue
    issue = 0
    created_issue = False
    if args.issue:
        issue = int(args.issue)
    elif not args.no_issue:
        if not common.gh_available():
            common.warn("gh not found; continuing without an issue")
        else:
            labels = ["sdlc", f"sdlc:lane-{lane.lower()}", "sdlc:stage-triage"]
            common.ensure_labels(labels)
            body = replace_template(
                common.read_text(common.SDLC_DIR / "templates" / "issue-logbook.md"),
                {
                    "<change-id>": change_id,
                    "<title>": args.title,
                    "<issue>": "TBD",
                    "<slug>": change_id,
                    "<lane>": lane,
                    "<M|S|L>": lane,
                    "<one-line>": args.reason,
                },
            )
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
                handle.write(body)
                tmp_body = handle.name
            try:
                label_args = []
                for label in labels:
                    label_args += ["--label", label]
                proc = common.gh(
                    [
                        "issue",
                        "create",
                        "--title",
                        f"[SDLC] {change_id} — {args.title}",
                        "--body-file",
                        tmp_body,
                        *label_args,
                    ]
                )
                url = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
                match = re.search(r"/issues/(\d+)", url)
                if not match:
                    common.die(f"cannot parse issue number from gh output: {url!r}")
                issue = int(match.group(1))
                created_issue = True
            finally:
                os.unlink(tmp_body)

    # 2. Branch and worktree
    slug = change_id
    prefix = str(issue) if issue else "local"
    branch = f"sdlc/{prefix}-{slug}"
    worktree_rel = f".worktrees/{prefix}-{slug}"
    worktree_abs = (common.REPO_ROOT / worktree_rel).resolve()

    if args.no_worktree:
        worktree_abs = common.REPO_ROOT
        worktree_rel = "."
    else:
        if worktree_abs.exists():
            common.die(f"worktree already exists: {worktree_abs}")
        base_ref = base_branch
        probe = common.run(["git", "rev-parse", "--verify", base_ref], check=False)
        if probe.returncode != 0:
            base_ref = f"origin/{base_branch}"
        exists = common.run(["git", "rev-parse", "--verify", branch], check=False)
        if exists.returncode == 0:
            common.run(["git", "worktree", "add", str(worktree_abs), branch])
        else:
            common.run(["git", "worktree", "add", "-b", branch, str(worktree_abs), base_ref])

    base_sha = common.run(["git", "rev-parse", "HEAD"], cwd=worktree_abs).stdout.strip()

    if lane in {"S", "L"} and not (worktree_abs / "openspec" / "config.yaml").exists():
        common.die(
            f"OpenSpec config missing in {worktree_abs}. "
            f"Commit the SDLC scaffold to {base_branch} before starting this change."
        )
    if not (worktree_abs / "scripts" / "sdlc" / "sdlc.py").exists():
        common.warn(
            "SDLC scripts are not present in the worktree; "
            f"commit the scaffold to {base_branch} before running agents there."
        )

    # 3. OpenSpec scaffold
    if lane in {"S", "L"}:
        ospec_dir = worktree_abs / "openspec" / "changes" / change_id
        if not ospec_dir.exists():
            if common.openspec_available():
                common.run(["openspec", "new", "change", change_id], cwd=worktree_abs)
            else:
                ospec_dir.mkdir(parents=True, exist_ok=True)
                write_file(ospec_dir / ".openspec.yaml", f"schema: spec-driven\ncreated: {date.today().isoformat()}\n")

    # 4. State
    state = common.new_state(
        change_id=change_id,
        title=args.title,
        issue=issue,
        lane=lane,
        reason=args.reason,
        branch=branch,
        worktree=worktree_rel,
        base_branch=base_branch,
        base_sha=base_sha,
        areas=areas,
        human_gates=human_gates,
    )
    state["worktree_abs"] = str(worktree_abs)
    runtime = worktree_abs / ".sdlc" / change_id
    for sub in ("reviews", "revisions", "evidence", "briefs"):
        (runtime / sub).mkdir(parents=True, exist_ok=True)
    write_file(runtime / "state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    # 5. Logbook
    if issue:
        body = replace_template(
            common.read_text(common.SDLC_DIR / "templates" / "issue-logbook.md"),
            {
                "<change-id>": change_id,
                "<title>": args.title,
                "<issue>": str(issue),
                "<slug>": slug,
                "<lane>": lane,
                "<M|S|L>": lane,
                "<one-line>": args.reason,
            },
        )
        if created_issue:
            with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
                handle.write(body)
                tmp_body = handle.name
            try:
                common.gh(["issue", "edit", str(issue), "--body-file", tmp_body])
            finally:
                os.unlink(tmp_body)
        else:
            common.issue_comment(
                issue,
                issue_state_block(state)
                + "\n\n"
                + f"SDLC tracking started for `{change_id}` (lane **{lane}**).\n\n"
                + f"- Branch: `{branch}`\n- Worktree: `{worktree_rel}`\n"
                + f"- Reason: {args.reason}\n",
            )
        append_event(
            state,
            stage="triage",
            round_no=0,
            actor="sdlc-conductor",
            verdict=None,
            summary=f"**SDLC start** — lane **{lane}**. Branch `{branch}`, worktree `{worktree_rel}`.",
        )

    print(json.dumps(
        {
            "change_id": change_id,
            "lane": lane,
            "issue": issue,
            "branch": branch,
            "worktree": str(worktree_abs),
            "state": str(runtime / "state.json"),
            "next": "scripts/sdlc/sdlc.sh next " + change_id,
        },
        indent=2,
    ))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if args.change:
        states = [common.load_state(args.change)]
    else:
        states = [
            json.loads((path / "state.json").read_text(encoding="utf-8"))
            for path in common.list_runtime_dirs()
        ]
    if not states:
        print("no SDLC changes")
        return 0

    for state in states:
        print(f"{state['change_id']}  lane={state['lane']}  issue=#{state['issue']}  "
              f"pr={('#' + str(state['pr'])) if state['pr'] else '-'}  status={state['status']}")
        print("  stage   status              rounds  last verdict         reviewer")
        for stage in ("spec", "plan", "dev"):
            data = state["stages"].get(stage)
            if not data or data["status"] == "skipped":
                continue
            print(
                f"  {stage:<7} {data['status']:<19} {data['rounds']:<7} "
                f"{str(data['last_verdict'] or '-'):<21} {data['last_reviewer'] or '-'}"
            )
        if state.get("escalation"):
            print(f"  escalation: {state['escalation'].get('reason')} — {state['escalation'].get('dossier', '')}")
        print()
    return 0


def next_action(state: dict) -> tuple[str, str, int, str]:
    """Return (role, stage, round, reason)."""
    status = state["status"]
    lane = state["lane"]
    stages = state["stages"]

    def role_for(stage: str, reviewing: bool) -> str:
        return common.STAGE_ROLES[stage][1 if reviewing else 0]

    if status == "triage":
        stage = "dev" if lane == "M" else "spec"
        return role_for(stage, False), stage, 1, "initial authoring"

    if status == "merge-ready":
        return "sdlc-merge-verifier", "merge", 0, "verify gates and build the dossier"

    if status == "escalated":
        return "human", "escalation", 0, state.get("escalation", {}).get("reason", "human decision")

    if status.endswith("-review"):
        stage = status[: -len("-review")]
        data = stages[stage]
        if data["status"] == "changes_requested":
            return (
                role_for(stage, False),
                stage,
                data["rounds"],
                f"revise findings from round {data['rounds']}",
            )
        if data["rounds"] >= common.cfg_int(common.load_config(), "SDLC_MAX_ROUNDS"):
            return "human", stage, data["rounds"], "rounds exhausted; escalate"
        return role_for(stage, True), stage, data["rounds"] + 1, "cold review"

    if status in {"spec", "plan", "dev"}:
        rounds = stages[status]["rounds"]
        if rounds == 0:
            return role_for(status, False), status, 1, "initial authoring"
        return role_for(status, False), status, rounds, f"revise findings from round {rounds}"

    return "human", status, 0, "unknown state"


def build_brief(state: dict, role: str, stage: str, round_no: int, reason: str) -> str:
    stage_artifact = {
        "spec": "openspec/changes/<id>/proposal.md + specs/** + tasks.md (Lane S)",
        "plan": "openspec/changes/<id>/design.md + tasks.md",
        "dev": "the PR diff",
        "merge": "all verdicts + the PR",
    }.get(stage, "the issue logbook")
    checklist = {
        "spec": "sdlc/checklists/spec.md",
        "plan": "sdlc/checklists/plan.md",
        "dev": "sdlc/checklists/dev.md",
        "merge": "sdlc/PROTOCOL.md §14 and all three checklists",
    }.get(stage, "sdlc/PROTOCOL.md")
    return f"""You are `{role}` for change `{state['change_id']}`.

- Stage: `{stage}`
- Round: `{round_no}` (max 3)
- Lane: `{state['lane']}`
- Issue: #{state['issue']}
- Worktree: `{state.get('worktree_abs', state['worktree'])}`
- Artifact under work: {stage_artifact.replace('<id>', state['change_id'])}
- Reviewed SHA: run `git rev-parse HEAD` in the worktree and record it in the verdict.
- Reason: {reason}

Read first, in this order:
1. `sdlc/PROTOCOL.md`
2. `openspec/config.yaml`
3. `{checklist}`
4. The issue logbook: `gh issue view {state['issue']} --json title,body,labels,comments`
5. The artifact at the reviewed SHA.
6. For round > 1: prior verdicts in `.sdlc/{state['change_id']}/reviews/` and the author's revision note.

Work only inside the worktree. Do not edit outside your role's allowed files.
Do not review your own work. Stop when your artifact or verdict is written.
"""


def cmd_next(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    role, stage, round_no, reason = next_action(state)
    brief = build_brief(state, role, stage, round_no, reason)
    brief_path = common.runtime_dir(args.change) / "briefs" / f"{stage}-r{round_no}-{role}.md"
    write_file(brief_path, brief)
    print(json.dumps(
        {
            "change_id": state["change_id"],
            "status": state["status"],
            "role": role,
            "stage": stage,
            "round": round_no,
            "reason": reason,
            "worktree": state.get("worktree_abs", state["worktree"]),
            "brief": str(brief_path),
        },
        indent=2,
    ))
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    stage = args.stage
    if stage not in state["stages"]:
        common.die(f"unknown stage {stage!r}")
    if state["stages"][stage]["status"] == "skipped":
        common.die(f"stage {stage!r} is skipped for lane {state['lane']}")
    if args.status == "in_progress":
        state["stages"][stage]["status"] = "in_progress"
        state["status"] = stage
    elif args.status == "in_review":
        state["stages"][stage]["status"] = "in_review"
        state["status"] = f"{stage}-review"
    else:
        common.die("status must be in_progress or in_review")
    state["stages"][stage]["updated_at"] = common.now_iso()
    common.save_state(args.change, state)
    append_event(
        state,
        stage=stage,
        round_no=state["stages"][stage]["rounds"],
        actor=args.actor or "sdlc-conductor",
        verdict=None,
        summary=f"**{stage}** → `{args.status}`.",
    )
    print(json.dumps({"change_id": args.change, "stage": stage, "status": args.status, "state": state["status"]}, indent=2))
    return 0


def cmd_verdict(args: argparse.Namespace) -> int:
    cfg = common.load_config()
    max_rounds = common.cfg_int(cfg, "SDLC_MAX_ROUNDS")
    state = common.load_state(args.change)
    stage = args.stage
    if stage not in state["stages"] or state["stages"][stage]["status"] == "skipped":
        common.die(f"stage {stage!r} is not active for lane {state['lane']}")

    verdict_file = Path(args.file).resolve()
    if not verdict_file.exists():
        common.die(f"verdict file not found: {verdict_file}")

    lint = common.run(
        [
            sys.executable,
            str(common.SDLC_DIR.parent / "scripts" / "sdlc" / "verdict-lint.py"),
            "--change",
            args.change,
            "--file",
            str(verdict_file),
            "--max-rounds",
            str(max_rounds),
        ],
        check=False,
    )
    print(lint.stdout, end="")
    if lint.returncode != 0:
        print(lint.stderr, end="", file=sys.stderr)
        common.die("verdict rejected by verdict-lint.py")

    verdict = common.read_json_block(common.read_text(verdict_file))
    expected_round = state["stages"][stage]["rounds"] + 1
    if args.round != expected_round:
        common.die(f"round {args.round} is not the next round (expected {expected_round})")
    if args.round > max_rounds:
        common.die(f"round {args.round} exceeds max {max_rounds}")

    data = state["stages"][stage]
    data["rounds"] = args.round
    data["last_verdict"] = verdict["verdict"]
    data["last_reviewer"] = verdict["reviewer"]
    data["last_sha"] = verdict["reviewed_sha"]
    data["updated_at"] = common.now_iso()

    if verdict["verdict"] == "APPROVE":
        data["status"] = "approved"
        advance_after_approval(state, stage)
    elif verdict["verdict"] == "CHANGES_REQUESTED":
        data["status"] = "changes_requested"
        state["status"] = f"{stage}-review"
    else:
        data["status"] = "escalated"
        state["status"] = "escalated"
        state["escalation"] = {
            "reason": "reviewer-escalation",
            "at": common.now_iso(),
            "dossier": str(verdict_file),
            "detail": verdict.get("summary", ""),
        }
    common.save_state(args.change, state)

    blocking = common.open_blocking(verdict.get("findings", []))
    append_event(
        state,
        stage=stage,
        round_no=args.round,
        actor=verdict["reviewer"],
        verdict=verdict["verdict"],
        summary=(
            f"**{stage} review r{args.round}** — `{verdict['verdict']}` "
            f"({len(blocking)} open blocker/major).\n\n{verdict.get('summary', '')}"
        ),
    )
    print(json.dumps(
        {
            "change_id": args.change,
            "stage": stage,
            "round": args.round,
            "verdict": verdict["verdict"],
            "open_blockers": len(blocking),
            "status": state["status"],
        },
        indent=2,
    ))
    return 0


def cmd_pr(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    number = args.number
    if not number:
        if not common.gh_available():
            common.die("gh is required to auto-detect the PR; pass --number")
        proc = common.gh(
            [
                "pr",
                "list",
                "--head",
                state["branch"],
                "--state",
                "all",
                "--json",
                "number,state,isDraft,headRefOid",
            ],
            check=False,
        )
        if proc.returncode != 0:
            common.die(f"cannot list PRs for branch {state['branch']}: {proc.stderr.strip()}")
        items = json.loads(proc.stdout or "[]")
        if not items:
            common.die(f"no PR found for branch {state['branch']}")
        number = sorted(items, key=lambda item: item["number"])[-1]["number"]
    state["pr"] = int(number)
    common.save_state(args.change, state)
    append_event(
        state,
        stage=state["status"],
        round_no=max((s["rounds"] for s in state["stages"].values()), default=0),
        actor="sdlc-conductor",
        verdict=None,
        summary=f"**PR linked** — #{number}.",
    )
    print(json.dumps({"change_id": args.change, "pr": state["pr"]}, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    failures = 0
    scripts = common.SDLC_DIR.parent / "scripts" / "sdlc"

    if state["lane"] in {"S", "L"}:
        if common.openspec_available():
            change_dir = common.openspec_change_dir(args.change)
            openspec_root = (
                change_dir.parents[2]
                if len(change_dir.parents) >= 3
                else common.REPO_ROOT
            )
            proc = common.run(
                ["openspec", "validate", args.change, "--strict", "--json"],
                cwd=openspec_root,
                check=False,
            )
            print(proc.stdout, end="")
            if proc.returncode != 0:
                print(proc.stderr, end="", file=sys.stderr)
                failures += 1
        else:
            common.warn("openspec CLI not found; skipped OpenSpec validation")

        proc = common.run(
            [sys.executable, str(scripts / "spec-lint.py"), "--change", args.change],
            check=False,
        )
        print(proc.stdout, end="")
        if proc.returncode != 0:
            print(proc.stderr, end="", file=sys.stderr)
            failures += 1

    proc = common.run(
        [sys.executable, str(scripts / "verdict-lint.py"), "--change", args.change],
        check=False,
    )
    print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, end="", file=sys.stderr)
        failures += 1

    print("check: " + ("PASS" if failures == 0 else f"FAIL ({failures} gate(s))"))
    return 0 if failures == 0 else 1


def _latest_required_verdicts(state: dict) -> list[tuple[str, dict]]:
    result = []
    for stage in LANE_STAGE_ORDER[state["lane"]]:
        verdict = common.latest_verdict(state["change_id"], stage)
        if verdict is None:
            result.append((stage, {"verdict": "MISSING", "findings": []}))
        else:
            result.append((stage, verdict))
    return result


def cmd_merge_ready(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    errors: list[str] = []

    for stage in LANE_STAGE_ORDER[state["lane"]]:
        data = state["stages"][stage]
        if data["status"] != "approved":
            errors.append(f"{stage}: status {data['status']!r}, expected approved")
        verdict = common.latest_verdict(state["change_id"], stage)
        if verdict is None:
            errors.append(f"{stage}: no verdict")
            continue
        if verdict.get("verdict") != "APPROVE":
            errors.append(f"{stage}: latest verdict {verdict.get('verdict')!r}")
        blocking = common.open_blocking(verdict.get("findings", []))
        if blocking:
            errors.append(f"{stage}: {len(blocking)} open blocker/major")
        if data["rounds"] > common.cfg_int(common.load_config(), "SDLC_MAX_ROUNDS"):
            errors.append(f"{stage}: {data['rounds']} rounds exceed max")

    check = common.run(
        [sys.executable, str(Path(__file__).resolve()), "check", args.change],
        check=False,
    )
    print(check.stdout, end="")
    if check.returncode != 0:
        errors.append("check gate failed")

    change_dir = common.openspec_change_dir(args.change)
    tasks_path = change_dir / "tasks.md"
    open_tasks = 0
    if state["lane"] in {"S", "L"}:
        if not tasks_path.exists():
            errors.append("tasks.md missing")
        else:
            text = tasks_path.read_text(encoding="utf-8")
            open_tasks = len(re.findall(r"^\s*-\s*\[\s\]\s+\d+\.\d+", text, re.MULTILINE))
            completed = len(re.findall(r"^\s*-\s*\[[xX]\]\s+\d+\.\d+", text, re.MULTILINE))
            if completed + open_tasks == 0:
                errors.append("tasks.md has no 'X.Y' checkbox tasks")
            if open_tasks and not args.allow_open_tasks:
                errors.append(f"{open_tasks} unchecked task(s) in tasks.md")
    if state["lane"] == "L" and not (change_dir / "design.md").exists():
        errors.append("design.md missing for lane L")

    if state.get("pr") and common.gh_available():
        view = common.run(
            ["gh", "pr", "view", str(state["pr"]), "--json", "state,isDraft,headRefOid,mergeable"],
            check=False,
        )
        if view.returncode == 0:
            info = json.loads(view.stdout or "{}")
            head = info.get("headRefOid") or ""
            reviewed = state["stages"]["dev"].get("last_sha") or ""
            if head and reviewed and not (head.startswith(reviewed) or reviewed.startswith(head)):
                errors.append(
                    f"PR head {head[:7]} does not match reviewed SHA {reviewed[:7]}"
                )
            if info.get("isDraft"):
                errors.append("PR is still a draft")
        else:
            common.warn(f"cannot read PR #{state['pr']}: {view.stderr.strip()}")

        checks = common.run(["gh", "pr", "checks", str(state["pr"])], check=False)
        print(checks.stdout, end="")
        if checks.returncode != 0:
            detail = (checks.stdout + checks.stderr).lower()
            if "no checks reported" in detail:
                common.warn("no CI checks reported for this PR; CI gate not verified")
            else:
                errors.append("gh pr checks reports failing or pending checks")
    else:
        common.warn("no PR number recorded; CI gate not verified")

    if errors:
        print(json.dumps({"ready": False, "errors": errors}, indent=2))
        return 1

    state["status"] = "merge-ready"
    common.save_state(args.change, state)

    # Dossier skeleton
    verdicts = _latest_required_verdicts(state)
    rows = "\n".join(
        f"| {stage.upper()} | {v.get('verdict')} (round {v.get('round', '-')}) | "
        f"`.sdlc/{args.change}/reviews/{stage}-r{v.get('round', '-')}.md` @ `{v.get('reviewed_sha', '-')}` |"
        for stage, v in verdicts
    )
    dossier = replace_template(
        common.read_text(common.SDLC_DIR / "templates" / "merge-dossier.md"),
        {"<change-id>": args.change},
    )
    dossier = re.sub(
        r"\| SPEC \| APPROVE \(round N\).*?\n\| DEV \| APPROVE \(round N\).*?\n",
        rows + "\n",
        dossier,
        flags=re.DOTALL,
    )
    write_file(common.runtime_dir(args.change) / "merge-dossier.md", dossier)
    append_event(
        state,
        stage="merge",
        round_no=0,
        actor="sdlc-conductor",
        verdict=None,
        summary="**merge-ready** — all gates green. Human decision required.",
    )
    print(json.dumps(
        {
            "ready": True,
            "change_id": args.change,
            "dossier": str(common.runtime_dir(args.change) / "merge-dossier.md"),
            "next": "dispatch sdlc-merge-verifier, then merge (delegated) or human gate",
        },
        indent=2,
    ))
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge a merge-ready PR under an explicit, recorded delegation.

    This is the only path that lets an agent merge. It refuses unless every
    automated gate is green and the delegation is named in writing.
    """
    if not args.delegated_by or not args.delegated_by.strip():
        common.die("auto-merge requires --delegated-by '<operator / reference>'")

    ready = cmd_merge_ready(
        argparse.Namespace(change=args.change, allow_open_tasks=False)
    )
    if ready != 0:
        common.die("merge-ready gate failed; refusing to merge")

    state = common.load_state(args.change)
    if state.get("escalation"):
        common.die("change is escalated; human decision required")
    if state["status"] != "merge-ready":
        common.die(f"status is {state['status']!r}, expected merge-ready")
    if not state.get("pr"):
        common.die("no PR linked; run `sdlc.sh pr <change>` first")
    if not common.gh_available():
        common.die("gh CLI is required for auto-merge")

    pr = str(state["pr"])
    view = common.run(
        ["gh", "pr", "view", pr, "--json", "state,isDraft,headRefOid,mergeable"],
        check=False,
    )
    if view.returncode != 0:
        common.die(f"cannot read PR #{pr}: {view.stderr.strip()}")
    info = json.loads(view.stdout or "{}")
    if info.get("state") != "OPEN":
        common.die(f"PR #{pr} state is {info.get('state')!r}, expected OPEN")
    if info.get("mergeable") not in (None, "MERGEABLE", "UNKNOWN"):
        common.die(f"PR #{pr} is not mergeable: {info.get('mergeable')}")
    if info.get("isDraft"):
        common.run(["gh", "pr", "ready", pr])
        common.log("PR marked ready for review")

    checks = common.run(["gh", "pr", "checks", pr], check=False)
    if checks.returncode != 0:
        detail = (checks.stdout + checks.stderr).lower()
        if "no checks reported" in detail:
            common.die("no CI checks reported; refusing full-auto merge without CI evidence")
        common.die(f"CI is not green on PR #{pr}")

    delegation = {
        "by": args.delegated_by.strip(),
        "at": common.now_iso(),
        "mode": "full-auto",
        "pr": state["pr"],
        "head_sha": info.get("headRefOid"),
    }
    state["merge_delegation"] = delegation
    common.save_state(args.change, state)
    common.gh(
        [
            "pr",
            "comment",
            pr,
            "--body",
            f"SDLC full-auto merge delegated by {delegation['by']} at {delegation['at']}.",
        ],
        check=False,
    )

    merge = common.run(
        ["gh", "pr", "merge", pr, "--merge", "--delete-branch"], check=False
    )
    if merge.returncode != 0:
        verify = common.run(["gh", "pr", "view", pr, "--json", "state"], check=False)
        merged = (
            verify.returncode == 0
            and json.loads(verify.stdout or "{}").get("state") == "MERGED"
        )
        if not merged:
            common.die(f"PR merge failed:\n{merge.stderr or merge.stdout}")

    main = common.main_repo_root()
    base = state["base_branch"]
    pull = common.run(["git", "-C", str(main), "pull", "--ff-only", "origin", base], check=False)
    if pull.returncode != 0:
        common.warn(f"could not fast-forward {base}; archive may be skipped")

    if state["lane"] in {"S", "L"} and common.openspec_available():
        change_dir = main / "openspec" / "changes" / args.change
        if change_dir.exists():
            common.run(["openspec", "archive", args.change, "--yes"], cwd=main, check=False)
        else:
            common.warn("OpenSpec change not present in the main checkout; archive skipped")

    state["status"] = "merged"
    dest = main / ".sdlc" / args.change
    dest.mkdir(parents=True, exist_ok=True)
    worktree = Path(state.get("worktree_abs", state["worktree"]))
    worktree_runtime = worktree / ".sdlc" / args.change
    if worktree_runtime.exists() and worktree_runtime.resolve() != dest.resolve():
        # The worktree may hold untracked verdicts/revision notes that were not
        # committed on the feature branch (they are meta-artifacts of the review).
        shutil.copytree(worktree_runtime, dest, dirs_exist_ok=True)
    write_file(dest / "state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    common.run(
        ["git", "-C", str(main), "add", "openspec", f".sdlc/{args.change}"],
        check=False,
    )
    dirty = common.run(["git", "-C", str(main), "status", "--porcelain"], check=False)
    if dirty.stdout.strip():
        common.run(
            [
                "git",
                "-C",
                str(main),
                "commit",
                "-m",
                f"chore({args.change}): archive merged change",
                "-m",
                "Co-Authored-By: Claude Code <noreply@anthropic.com>",
            ],
            check=False,
        )
        common.run(["git", "-C", str(main), "push", "origin", base], check=False)

    if state.get("issue"):
        common.gh(
            [
                "issue",
                "close",
                str(state["issue"]),
                "--comment",
                f"Merged under full-auto delegation by {delegation['by']}.",
            ],
            check=False,
        )

    worktree = Path(state.get("worktree_abs", state["worktree"]))
    if worktree != main and worktree.exists():
        common.run(
            ["git", "-C", str(main), "worktree", "remove", str(worktree), "--force"],
            check=False,
        )

    print(
        json.dumps(
            {
                "change_id": args.change,
                "merged": True,
                "pr": state["pr"],
                "delegated_by": delegation["by"],
            },
            indent=2,
        )
    )
    return 0


def cmd_escalate(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    state["status"] = "escalated"
    state["escalation"] = {
        "reason": args.reason,
        "at": common.now_iso(),
        "dossier": args.dossier or "",
        "detail": args.detail or "",
    }
    common.save_state(args.change, state)
    if common.gh_available() and state.get("issue"):
        common.ensure_labels(["sdlc:escalated"])
        common.gh(["issue", "edit", str(state["issue"]), "--add-label", "sdlc:escalated"], check=False)
    append_event(
        state,
        stage=state["status"],
        round_no=0,
        actor="sdlc-conductor",
        verdict="ESCALATE",
        summary=f"**Escalation** — `{args.reason}`.\n\n{args.detail or ''}",
    )
    print(json.dumps({"change_id": args.change, "escalated": True, "reason": args.reason}, indent=2))
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    state = common.load_state(args.change)
    main = common.main_repo_root()
    current_runtime = common.runtime_dir(args.change)
    dest = main / ".sdlc" / args.change
    if current_runtime.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(current_runtime, dest, dirs_exist_ok=True)

    state["status"] = "merged" if args.merged else "abandoned"
    write_file(dest / "state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")

    if args.merged and state["lane"] in {"S", "L"} and common.openspec_available():
        if (main / "openspec" / "changes" / args.change).exists():
            common.run(["openspec", "archive", args.change, "--yes"], cwd=main, check=False)
        else:
            common.warn(
                "OpenSpec change not present in the main checkout; "
                "pull the merged PR before archiving"
            )

    worktree_abs = Path(state.get("worktree_abs", state["worktree"]))
    if not args.keep_worktree and worktree_abs != main and worktree_abs.exists():
        common.run(
            ["git", "-C", str(main), "worktree", "remove", str(worktree_abs), "--force"],
            check=False,
        )

    if args.merged and common.gh_available() and state.get("issue"):
        common.gh(["issue", "close", str(state["issue"]), "--comment", "Merged."], check=False)
    print(json.dumps({"change_id": args.change, "status": state["status"], "ledger": str(dest)}, indent=2))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    checks: list[dict[str, str | bool]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": ok, "detail": detail})

    check("git repository", (common.REPO_ROOT / ".git").exists())
    check("python >= 3.10", sys.version_info >= (3, 10), sys.version.split()[0])
    check("gh installed", common.have("gh"))
    if common.have("gh"):
        auth = common.run(["gh", "auth", "status"], check=False)
        check(
            "gh authenticated",
            auth.returncode == 0,
            "authenticated" if auth.returncode == 0 else (auth.stderr or auth.stdout).strip()[:200],
        )
    check("openspec installed", common.have("openspec"))
    check("openspec config", (common.REPO_ROOT / "openspec" / "config.yaml").exists())
    check("agent profiles", bool(list((common.SDLC_DIR / "agents").glob("*.md"))))
    sync = common.run(
        [sys.executable, str(common.SDLC_DIR.parent / "scripts" / "sdlc" / "install_agents.py"), "--check"],
        check=False,
    )
    check("agent adapters in sync", sync.returncode == 0, sync.stdout.strip()[:200])
    check("CI workflows", (common.REPO_ROOT / ".github" / "workflows" / "sdlc-checks.yml").exists())
    ignored = (common.REPO_ROOT / ".gitignore").read_text(encoding="utf-8") if (common.REPO_ROOT / ".gitignore").exists() else ""
    check(".worktrees ignored", ".worktrees/" in ignored)
    check("review card linter", (common.SDLC_DIR.parent / "scripts" / "sdlc" / "spec-lint.py").exists())

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({"ok": not failed, "checks": checks}, indent=2))
    return 0 if not failed else 1


def cmd_lanes(_: argparse.Namespace) -> int:
    print("""Lane M — micro: no SPEC, no PLAN, dev + one cold dev review.
  all: <=2 files, one module, no contract/money/risk/vault change, existing tests cover it.
Lane S — standard: SPEC (proposal + delta specs + tasks), dev + cold spec/dev reviews.
  any: new behavior, 3-10 files, additive contract, new config/UI.
Lane L — large: SPEC, PLAN (design + tasks), dev + cold spec/plan/dev reviews.
  any: breaking contract, money/risk/vault path, >10 files, cross-stack, migration, ADR.
Tie or uncertainty -> higher lane.""")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="create issue + worktree + branch + state")
    p.add_argument("change")
    p.add_argument("--title", required=True)
    p.add_argument("--lane", required=True, choices=["M", "S", "L", "m", "s", "l"])
    p.add_argument("--reason", required=True)
    p.add_argument("--issue", type=int)
    p.add_argument("--areas", help="comma-separated areas")
    p.add_argument("--human-gates", help="comma-separated: spec,plan,merge")
    p.add_argument("--base-branch")
    p.add_argument("--no-issue", action="store_true")
    p.add_argument("--no-worktree", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("status", help="show state")
    p.add_argument("change", nargs="?")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", help="print the next action and write a brief")
    p.add_argument("change")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("stage", help="mark a stage in_progress or in_review")
    p.add_argument("change")
    p.add_argument("stage", choices=["spec", "plan", "dev"])
    p.add_argument("status", choices=["in_progress", "in_review"])
    p.add_argument("--actor")
    p.set_defaults(func=cmd_stage)

    p = sub.add_parser("verdict", help="record a verdict file")
    p.add_argument("change")
    p.add_argument("stage", choices=["spec", "plan", "dev"])
    p.add_argument("round", type=int)
    p.add_argument("file")
    p.set_defaults(func=cmd_verdict)

    p = sub.add_parser("pr", help="link the change to its PR")
    p.add_argument("change")
    p.add_argument("--number", type=int)
    p.set_defaults(func=cmd_pr)

    p = sub.add_parser("check", help="run OpenSpec, spec, and verdict lints")
    p.add_argument("change")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("merge-ready", help="verify every gate and build the dossier")
    p.add_argument("change")
    p.add_argument("--allow-open-tasks", action="store_true")
    p.set_defaults(func=cmd_merge_ready)

    p = sub.add_parser("merge", help="merge under an explicit recorded delegation")
    p.add_argument("change")
    p.add_argument(
        "--delegated-by",
        required=True,
        help="operator or reference that explicitly authorized the merge",
    )
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("escalate", help="record a human escalation")
    p.add_argument("change")
    p.add_argument("--reason", required=True)
    p.add_argument("--detail")
    p.add_argument("--dossier")
    p.set_defaults(func=cmd_escalate)

    p = sub.add_parser("close", help="close a change")
    p.add_argument("change")
    p.add_argument("--merged", action="store_true")
    p.add_argument("--keep-worktree", action="store_true")
    p.set_defaults(func=cmd_close)

    p = sub.add_parser("doctor", help="check prerequisites and adapter sync")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("lanes", help="print the lane rubric")
    p.set_defaults(func=cmd_lanes)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
