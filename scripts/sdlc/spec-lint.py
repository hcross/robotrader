#!/usr/bin/env python3
"""Validate an OpenSpec change against the Robotrader SDLC spec rules.

Checks the human five-minute Review Card, the OpenSpec delta contract, the
tasks format, and (when available) runs `openspec validate --strict`.

Usage:
    scripts/sdlc/spec-lint.py --change <change-id>
    scripts/sdlc/spec-lint.py --change <change-id> --json
    scripts/sdlc/spec-lint.py --path openspec/changes/<change-id>

Exit codes: 0 pass, 1 errors, 2 warnings under --strict.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

REQUIRED_PROPOSAL_SECTIONS = ("Why", "What Changes", "Capabilities", "Non-goals", "Impact")
REQUIRED_DESIGN_SECTIONS = (
    "Context",
    "Goals / Non-Goals",
    "Decisions",
    "Risks / Trade-offs",
    "Migration Plan",
    "Open Questions",
)
REQUIRED_CARD_FIELDS = ("Outcome", "Why now", "Blast radius", "Risk", "Effort", "Decision needed")
BANNED = ("TBD", "TODO", "FIXME", "???")
DIAGRAM_ASCII = re.compile(r"(?:┌|└|├|│|─|┼|╔|╚|╠|║|╗|╝|\+--)")


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


def section(text: str, title: str) -> str:
    """Return the body of a heading, stopping at the next heading of same/higher level."""
    pattern = re.compile(
        rf"^(#{{1,6}})\s+{re.escape(title)}(?:\s.*)?$", re.IGNORECASE | re.MULTILINE
    )
    match = pattern.search(text)
    if not match:
        return ""
    level = len(match.group(1))
    start = match.end()
    stop = len(text)
    for nxt in re.finditer(r"^(#{1,6})\s+.+$", text[start:], re.MULTILINE):
        if len(nxt.group(1)) <= level:
            stop = start + nxt.start()
            break
    return text[start:stop]


def has_heading(text: str, title: str, level: int | None = None) -> bool:
    hashes = "#" * level if level else "#{1,6}"
    return bool(
        re.search(
            rf"^{hashes}\s+{re.escape(title)}(?:\s.*)?$", text, re.IGNORECASE | re.MULTILINE
        )
    )


def strip_code_blocks(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    return text


def count_words(text: str) -> int:
    plain = strip_code_blocks(text)
    plain = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", plain)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"[`*_>#|]", " ", plain)
    return len(re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9'’_-]*", plain))


def count_diagrams(text: str) -> int:
    mermaid = len(re.findall(r"```mermaid\b", text, re.IGNORECASE))
    ascii_blocks = len(DIAGRAM_ASCII.findall(strip_fenced(text)))
    return mermaid + (1 if ascii_blocks else 0)


def strip_fenced(text: str) -> str:
    return re.sub(r"```.*?```", " ", text, flags=re.DOTALL)


def parse_requirements(spec_text: str) -> list[dict]:
    delta_headers = [
        (match.start(), match.group(1).upper())
        for match in re.finditer(
            r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$",
            spec_text,
            re.MULTILINE | re.IGNORECASE,
        )
    ]

    def delta_for(position: int) -> str:
        current = "UNKNOWN"
        for start, name in delta_headers:
            if start < position:
                current = name
            else:
                break
        return current

    matches = list(re.finditer(r"^###\s+Requirement:\s*(.+?)\s*$", spec_text, re.MULTILINE | re.IGNORECASE))
    requirements = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(spec_text)
        body = spec_text[start:end]
        scenarios = []
        scenario_matches = list(
            re.finditer(r"^####\s+Scenario:\s*(.+?)\s*$", body, re.MULTILINE | re.IGNORECASE)
        )
        for s_index, s_match in enumerate(scenario_matches):
            s_start = s_match.end()
            s_end = (
                scenario_matches[s_index + 1].start()
                if s_index + 1 < len(scenario_matches)
                else len(body)
            )
            s_body = body[s_start:s_end]
            scenarios.append(
                {
                    "name": s_match.group(1).strip(),
                    "when": bool(re.search(r"\*\*WHEN\*\*", s_body, re.IGNORECASE)),
                    "then": bool(re.search(r"\*\*THEN\*\*", s_body, re.IGNORECASE)),
                }
            )
        requirements.append(
            {
                "name": match.group(1).strip(),
                "delta": delta_for(match.start()),
                "scenarios": scenarios,
                "body": body,
            }
        )
    return requirements


def open_questions_are_empty(design_text: str) -> bool:
    body = section(design_text, "Open Questions")
    cleaned = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    return cleaned == ""


def lint(
    change_id: str,
    change_dir: Path,
    lane: str,
    max_card_words: int,
    skip_openspec: bool = False,
) -> Report:
    report = Report()
    proposal = change_dir / "proposal.md"
    specs_dir = change_dir / "specs"
    design = change_dir / "design.md"
    tasks = change_dir / "tasks.md"

    if lane == "M":
        report.warning("lane M should not carry an OpenSpec change; use the issue + PR only")
        return report

    # Required files
    if not proposal.exists():
        report.error("missing proposal.md")
        return report
    if not specs_dir.exists() or not any(specs_dir.rglob("spec.md")):
        report.error("missing specs/<capability>/spec.md")
    if lane == "L" and not design.exists():
        report.warning("design.md not present yet (PLAN stage); merge-ready will require it")
    if not tasks.exists():
        if lane == "S":
            report.error("missing tasks.md")
        else:
            report.warning("tasks.md not present yet (PLAN stage)")

    proposal_text = proposal.read_text(encoding="utf-8")

    # Proposal required sections
    for title in REQUIRED_PROPOSAL_SECTIONS:
        if not has_heading(proposal_text, title, level=2):
            report.error(f"proposal.md missing section: {title}")

    # Review Card
    card = section(proposal_text, "Review Card")
    if not card:
        report.error("proposal.md missing '## Review Card (≤ 5 min)'")
    else:
        for field in REQUIRED_CARD_FIELDS:
            if field.lower() not in card.lower():
                report.error(f"Review Card missing field: {field}")
        words = count_words(card)
        diagrams = count_diagrams(card)
        read_minutes = words / 200.0 + 0.5 * diagrams
        report.note(f"Review Card: {words} words, {diagrams} diagram(s), ~{read_minutes:.1f} min")
        if words > max_card_words:
            report.error(f"Review Card is {words} words (max {max_card_words})")
        if diagrams < 1:
            report.error("Review Card needs at least one Mermaid or ASCII diagram")
        if read_minutes > 5.0:
            report.error(f"Review Card read time is {read_minutes:.1f} min (max 5.0)")

    # Banned placeholders
    for token in BANNED:
        if token in proposal_text:
            report.error(f"proposal.md contains placeholder {token!r}")

    # Specs
    spec_count = 0
    for spec_file in sorted(specs_dir.rglob("spec.md")) if specs_dir.exists() else []:
        spec_count += 1
        requirement_names: set[str] = set()
        text = spec_file.read_text(encoding="utf-8")
        rel = spec_file.relative_to(change_dir)
        if not re.search(r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$", text, re.MULTILINE):
            report.error(f"{rel}: missing a delta header (## ADDED/MODIFIED/REMOVED/RENAMED Requirements)")
        for token in BANNED:
            if token in text:
                report.error(f"{rel}: contains placeholder {token!r}")
        requirements = parse_requirements(text)
        if not requirements:
            report.error(f"{rel}: no '### Requirement:' found")
            continue
        scenario_names: set[str] = set()
        for requirement in requirements:
            name = requirement["name"]
            delta = requirement["delta"]
            if name in requirement_names:
                report.error(f"{rel}: duplicate requirement name {name!r}")
            requirement_names.add(name)
            if delta == "UNKNOWN":
                report.error(f"{rel}: requirement {name!r} is outside a delta header")
            if delta == "REMOVED":
                if not re.search(r"\*\*Reason\*\*", requirement["body"], re.IGNORECASE):
                    report.error(f"{rel}: removed requirement {name!r} has no **Reason**")
                if not re.search(r"\*\*Migration\*\*", requirement["body"], re.IGNORECASE):
                    report.error(f"{rel}: removed requirement {name!r} has no **Migration**")
                continue
            if not re.search(r"\b(SHALL|MUST)\b", requirement["body"]):
                report.error(f"{rel}: requirement {name!r} does not use SHALL or MUST")
            if not requirement["scenarios"]:
                report.error(f"{rel}: requirement {name!r} has no '#### Scenario:'")
                continue
            for scenario in requirement["scenarios"]:
                if scenario["name"] in scenario_names:
                    report.error(f"{rel}: duplicate scenario name {scenario['name']!r}")
                scenario_names.add(scenario["name"])
                if not scenario["when"] or not scenario["then"]:
                    report.error(
                        f"{rel}: scenario {scenario['name']!r} needs both **WHEN** and **THEN**"
                    )
    if spec_count == 0:
        report.error("no spec files found")

    # Design
    if design.exists():
        design_text = design.read_text(encoding="utf-8")
        for title in REQUIRED_DESIGN_SECTIONS:
            if not has_heading(design_text, title, level=2):
                report.error(f"design.md missing section: {title}")
        if count_diagrams(design_text) < 1:
            report.error("design.md needs at least one Mermaid or ASCII diagram")
        if not open_questions_are_empty(design_text):
            report.error("design.md 'Open Questions' must be empty before approval")
        for token in BANNED:
            if token in design_text:
                report.error(f"design.md contains placeholder {token!r}")

    # Tasks
    if tasks.exists():
        task_text = tasks.read_text(encoding="utf-8")
        unchecked = len(re.findall(r"^\s*-\s*\[\s\]\s+\d+\.\d+", task_text, re.MULTILINE))
        checked = len(re.findall(r"^\s*-\s*\[[xX]\]\s+\d+\.\d+", task_text, re.MULTILINE))
        loose = [
            line
            for line in task_text.splitlines()
            if line.strip().startswith("- [") and not re.match(r"^\s*-\s*\[[ xX]\]\s+\d+\.\d+", line)
        ]
        if checked + unchecked == 0:
            if lane == "S":
                report.error("tasks.md has no 'X.Y' checkbox tasks")
            else:
                report.warning("tasks.md has no tasks yet (PLAN stage)")
        if loose:
            report.warning(f"tasks.md has {len(loose)} non-conforming checkbox line(s)")
        if not has_heading(task_text, "Verification", level=2):
            report.warning("tasks.md missing '## Verification'")
        if unchecked:
            report.warning(f"tasks.md has {unchecked} unchecked task(s)")
        report.note(f"tasks: {checked} done, {unchecked} open")

    # OpenSpec strict validation
    if skip_openspec:
        report.note("openspec validate: skipped (--skip-openspec)")
    elif common.openspec_available():
        openspec_root = (
            change_dir.parents[2] if len(change_dir.parents) >= 3 else common.REPO_ROOT
        )
        proc = subprocess.run(
            ["openspec", "validate", change_id, "--strict", "--json"],
            cwd=str(openspec_root),
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            detail = (proc.stdout or proc.stderr or "").strip()
            report.error(f"openspec validate --strict failed:\n{detail}")
        else:
            report.note("openspec validate --strict: pass")
    else:
        report.warning("openspec CLI not found; skipped OpenSpec validation")

    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--change", help="change id")
    parser.add_argument("--path", help="explicit change directory")
    parser.add_argument("--lane", choices=["M", "S", "L"], help="override lane")
    parser.add_argument("--max-card-words", type=int, default=400)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true", help="fail on warnings")
    parser.add_argument("--skip-openspec", action="store_true", help="do not call the openspec CLI")
    args = parser.parse_args(argv)

    if args.path:
        change_dir = Path(args.path).resolve()
        change_id = change_dir.name
    elif args.change:
        change_id = args.change
        change_dir = common.openspec_change_dir(change_id)
    else:
        parser.error("one of --change or --path is required")

    if not change_dir.exists():
        common.die(f"change directory not found: {change_dir}")

    lane = args.lane
    if not lane:
        if common.state_path(change_id).exists():
            lane = common.load_state(change_id)["lane"]
        else:
            lane = "S"
            common.warn(
                f"no SDLC state for {change_id}; assuming lane S "
                "(pass --lane to override)"
            )

    report = lint(change_id, change_dir, lane, args.max_card_words, args.skip_openspec)

    if args.as_json:
        print(
            json.dumps(
                {
                    "change_id": change_id,
                    "lane": lane,
                    "ok": report.ok(),
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "info": report.info,
                },
                indent=2,
            )
        )
    else:
        print(f"spec-lint: {change_id} (lane {lane})")
        for line in report.info:
            print(f"  info   {line}")
        for line in report.warnings:
            print(f"  warn   {line}")
        for line in report.errors:
            print(f"  ERROR  {line}")
        print("  result " + ("PASS" if report.ok() else "FAIL"))

    if not report.ok():
        return 1
    if args.strict and report.warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
