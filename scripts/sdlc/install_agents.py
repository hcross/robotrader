#!/usr/bin/env python3
"""Install the canonical SDLC agent profiles into the Claude Code and
Antigravity CLI adapter directories.

Canonical source: sdlc/agents/*.md
Claude Code:      .claude/agents/*.md
Antigravity CLI:  .agent/agents/*.md + .agent/agents.json

Usage:
    scripts/sdlc/install-agents.sh            # write adapters
    scripts/sdlc/install-agents.sh --check    # fail if adapters drift
    scripts/sdlc/install-agents.sh --global   # also install to ~/.claude/agents and ~/.gemini/agents
    scripts/sdlc/install-agents.sh --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HEADER = (
    "<!-- GENERATED FILE — source: sdlc/agents/{name}.md. "
    "Run scripts/sdlc/install-agents.sh to update. Do not edit. -->"
)
FRONTMATTER_RE = re.compile(r"^(---\n.*?\n---\n)", re.DOTALL)


def source_agents() -> list[Path]:
    return sorted((common.SDLC_DIR / "agents").glob("*.md"))


def render(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        common.die(f"{source.name}: missing YAML frontmatter")
    front = match.group(1)
    name_match = re.search(r"^name:\s*(.+?)\s*$", front, re.MULTILINE)
    if not name_match:
        common.die(f"{source.name}: frontmatter missing 'name'")
    name = name_match.group(1).strip().strip('"').strip("'")
    if name != source.stem:
        common.die(f"{source.name}: frontmatter name {name!r} does not match filename")
    header = HEADER.format(name=name)
    return front + header + "\n" + text[match.end():]


def targets() -> list[Path]:
    return [
        common.REPO_ROOT / ".claude" / "agents",
        common.REPO_ROOT / ".agent" / "agents",
    ]


def global_targets() -> list[Path]:
    return [
        Path.home() / ".claude" / "agents",
        Path.home() / ".gemini" / "agents",
    ]


def write_manifest() -> str:
    return json.dumps({"entries": [{"path": "agents"}]}, indent=2) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify adapters are in sync")
    parser.add_argument("--global", dest="install_global", action="store_true", help="install to user-level CLI dirs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    sources = source_agents()
    if not sources:
        common.die(f"no agent profiles in {common.SDLC_DIR / 'agents'}")

    rendered = {source.stem: render(source) for source in sources}
    drift: list[str] = []
    written: list[str] = []

    all_targets = targets() + (global_targets() if args.install_global else [])
    for target_dir in all_targets:
        for name, content in rendered.items():
            destination = target_dir / f"{name}.md"
            if args.check:
                if not destination.exists():
                    drift.append(f"missing {destination}")
                elif destination.read_text(encoding="utf-8") != content:
                    drift.append(f"drift {destination}")
                continue
            if args.dry_run:
                print(f"would write {destination}")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
            written.append(str(destination))

    # Antigravity manifest (project-level only)
    manifest = common.REPO_ROOT / ".agent" / "agents.json"
    if args.check:
        if not manifest.exists():
            drift.append(f"missing {manifest}")
        elif manifest.read_text(encoding="utf-8") != write_manifest():
            drift.append(f"drift {manifest}")
    elif not args.dry_run:
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(write_manifest(), encoding="utf-8")
        written.append(str(manifest))

    if args.check:
        if drift:
            print("install-agents: DRIFT")
            for item in drift:
                print(f"  {item}")
            print("run scripts/sdlc/install-agents.sh")
            return 1
        print(f"install-agents: OK ({len(sources)} profiles, {len(all_targets)} target dirs)")
        return 0

    if args.dry_run:
        print(f"install-agents: dry-run ({len(sources)} profiles)")
        return 0

    print(f"install-agents: wrote {len(written)} file(s) for {len(sources)} profiles")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
