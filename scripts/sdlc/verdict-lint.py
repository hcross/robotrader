#!/usr/bin/env python3
"""Validate an SDLC review verdict and enforce the 3-round closure rules.

Usage:
    scripts/sdlc/verdict-lint.py --change <change-id> --all
    scripts/sdlc/verdict-lint.py --change <change-id> --file .sdlc/<id>/reviews/spec-r1.md
    scripts/sdlc/verdict-lint.py --file <path> --json

Exit codes: 0 pass, 1 errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

FILENAME_RE = re.compile(r"^(spec|plan|dev)-r(\d+)\.md$")
FINDING_RE = re.compile(r"^(SPEC|PLAN|DEV)-R([1-3])-F(\d{2,3})$")
STAGE_PREFIX = {"spec": "SPEC", "plan": "PLAN", "dev": "DEV"}
ROLE_TO_STAGE = {
    "sdlc-spec-reviewer": "spec",
    "sdlc-plan-reviewer": "plan",
    "sdlc-dev-reviewer": "dev",
}
SEVERITIES = {"blocker", "major", "minor", "nit"}
ORIGINS = {"initial", "regression", "security", "critical"}
STATUSES = {"open", "closed", "regressed"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.info.append(message)

    def ok(self) -> bool:
        return not self.errors


def parse_filename(path: Path) -> tuple[str, int] | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def validate_file(path: Path, change_id: str, max_rounds: int, report: Report) -> dict | None:
    parsed = parse_filename(path)
    if not parsed:
        report.error(f"{path.name}: expected <stage>-r<N>.md")
        return None
    stage, round_no = parsed
    if round_no > max_rounds:
        report.error(f"{path.name}: round {round_no} exceeds max {max_rounds}")
    try:
        verdict = common.read_json_block(common.read_text(path))
    except (ValueError, json.JSONDecodeError) as exc:
        report.error(f"{path.name}: cannot parse machine verdict: {exc}")
        return None

    required = (
        "schema",
        "change_id",
        "stage",
        "round",
        "reviewer",
        "reviewed_sha",
        "verdict",
        "summary",
        "findings",
        "closed",
    )
    for key in required:
        if key not in verdict:
            report.error(f"{path.name}: missing field {key!r}")
    if report.errors:
        return verdict

    if verdict["schema"] != "sdlc.verdict/v1":
        report.error(f"{path.name}: schema must be 'sdlc.verdict/v1'")
    if verdict["change_id"] != change_id:
        report.error(f"{path.name}: change_id {verdict['change_id']!r} != {change_id!r}")
    if verdict["stage"] != stage:
        report.error(f"{path.name}: stage {verdict['stage']!r} != filename stage {stage!r}")
    if verdict["round"] != round_no:
        report.error(f"{path.name}: round {verdict['round']!r} != filename round {round_no}")
    if verdict["reviewer"] not in ROLE_TO_STAGE:
        report.error(f"{path.name}: unknown reviewer {verdict['reviewer']!r}")
    elif ROLE_TO_STAGE[verdict["reviewer"]] != stage:
        report.error(
            f"{path.name}: reviewer {verdict['reviewer']!r} is not the {stage} reviewer"
        )
    if not str(verdict["reviewed_sha"]).strip():
        report.error(f"{path.name}: reviewed_sha is empty")
    if verdict["verdict"] not in {"APPROVE", "CHANGES_REQUESTED", "ESCALATE"}:
        report.error(f"{path.name}: invalid verdict {verdict['verdict']!r}")
    if not str(verdict["summary"]).strip():
        report.error(f"{path.name}: summary is empty")

    findings = verdict["findings"]
    if not isinstance(findings, list):
        report.error(f"{path.name}: findings must be a list")
        return verdict

    seen: set[str] = set()
    for finding in findings:
        fid = finding.get("id", "<missing>")
        if not FINDING_RE.match(fid):
            report.error(f"{path.name}: invalid finding id {fid!r}")
            continue
        if fid in seen:
            report.error(f"{path.name}: duplicate finding id {fid!r}")
        seen.add(fid)
        if not fid.startswith(STAGE_PREFIX[stage] + "-"):
            report.error(f"{path.name}: finding {fid!r} does not match stage {stage!r}")
        if finding.get("severity") not in SEVERITIES:
            report.error(f"{path.name}: {fid}: invalid severity")
        if finding.get("origin") not in ORIGINS:
            report.error(f"{path.name}: {fid}: invalid origin")
        if finding.get("status") not in STATUSES:
            report.error(f"{path.name}: {fid}: invalid status")
        for key in ("location", "evidence", "required_fix"):
            if not str(finding.get(key, "")).strip():
                report.error(f"{path.name}: {fid}: {key} is empty")

    blocking = common.open_blocking(findings)
    if verdict["verdict"] == "APPROVE" and blocking:
        report.error(f"{path.name}: APPROVE with {len(blocking)} open blocker/major")
    if verdict["verdict"] == "CHANGES_REQUESTED" and not blocking:
        report.error(f"{path.name}: CHANGES_REQUESTED with no open blocker/major")
    if verdict["verdict"] == "CHANGES_REQUESTED" and round_no >= max_rounds:
        report.error(f"{path.name}: round {round_no} must ESCALATE, not request changes")

    # Prior rounds: closure rules
    prior_files = [p for p in common.verdict_files(change_id, stage) if p != path and (parse_filename(p) or ("", 0))[1] < round_no]
    prior_open: dict[str, dict] = {}
    prior_closed: set[str] = set()
    prior_ids: set[str] = set()
    for prior_path in prior_files:
        try:
            prior = common.read_json_block(common.read_text(prior_path))
        except (ValueError, json.JSONDecodeError):
            report.warning(f"{path.name}: cannot read prior {prior_path.name}; closure not checked")
            continue
        for finding in prior.get("findings", []):
            fid = finding.get("id", "")
            prior_ids.add(fid)
            if finding.get("status") in {"open", "regressed"}:
                prior_open[fid] = finding
            elif finding.get("status") == "closed":
                prior_open.pop(fid, None)
                prior_closed.add(fid)

    if round_no > 1:
        current_by_id = {finding.get("id"): finding for finding in findings}
        for fid in prior_open:
            if fid not in current_by_id and fid not in set(verdict["closed"]):
                report.error(
                    f"{path.name}: prior open finding {fid} is neither re-evaluated nor closed"
                )
        for fid in verdict["closed"]:
            if fid not in prior_ids:
                report.error(f"{path.name}: closed id {fid} was not a prior finding")
        for finding in findings:
            fid = finding.get("id", "")
            if fid not in prior_ids and finding.get("origin") not in {
                "regression",
                "security",
                "critical",
            }:
                report.error(
                    f"{path.name}: new finding {fid} must be regression/security/critical after R1"
                )
        for fid in prior_closed:
            current = current_by_id.get(fid)
            if current and current.get("status") in {"open", "regressed"} and current.get("origin") == "initial":
                report.error(f"{path.name}: closed finding {fid} reopened without a new origin")

    for finding in findings:
        fid = finding.get("id", "")
        match = FINDING_RE.match(fid)
        if match and fid not in prior_ids and int(match.group(2)) != round_no:
            report.error(
                f"{path.name}: new finding {fid} must use round {round_no} in its id"
            )

    if round_no == 1:
        for finding in findings:
            if finding.get("origin") != "initial":
                report.error(
                    f"{path.name}: round 1 finding {finding.get('id')} must have origin 'initial'"
                )

    report.note(
        f"{path.name}: {verdict['verdict']} — "
        f"{len(blocking)} open blocker/major, {len(findings)} finding(s)"
    )
    return verdict


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change")
    parser.add_argument("--file")
    parser.add_argument("--stage", choices=["spec", "plan", "dev"])
    parser.add_argument("--round", type=int)
    parser.add_argument("--all", action="store_true", help="validate every verdict of the change")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-rounds", type=int, default=None)
    args = parser.parse_args(argv)

    cfg = common.load_config()
    max_rounds = args.max_rounds or common.cfg_int(cfg, "SDLC_MAX_ROUNDS")
    report = Report()

    if args.file:
        path = Path(args.file).resolve()
        if not path.exists():
            common.die(f"verdict not found: {path}")
        parsed = parse_filename(path)
        if not parsed:
            common.die(f"invalid verdict filename: {path.name}")
        change_id = args.change or path.parent.parent.name
        if args.stage and args.stage != parsed[0]:
            common.die(f"--stage {args.stage} does not match filename {path.name}")
        if args.round and args.round != parsed[1]:
            common.die(f"--round {args.round} does not match filename {path.name}")
        validate_file(path, change_id, max_rounds, report)
    elif args.change:
        change_id = args.change
        paths = common.verdict_files(change_id, args.stage)
        if not paths:
            report.warning(f"no verdicts found for {change_id}")
        for path in paths:
            validate_file(path, change_id, max_rounds, report)
    else:
        parser.error("one of --change or --file is required")

    if args.as_json:
        print(
            json.dumps(
                {
                    "ok": report.ok(),
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "info": report.info,
                },
                indent=2,
            )
        )
    else:
        for line in report.info:
            print(f"  info   {line}")
        for line in report.warnings:
            print(f"  warn   {line}")
        for line in report.errors:
            print(f"  ERROR  {line}")
        print("  result " + ("PASS" if report.ok() else "FAIL"))

    return 0 if report.ok() else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
