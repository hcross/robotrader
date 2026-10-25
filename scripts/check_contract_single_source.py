#!/usr/bin/env python3
"""Reject duplicate declarations of the shared policy contract keys.

The safe-baseline TTL must be declared exactly once, as
``SAFE_BASELINE_TTL_SECONDS`` in ``contracts/policy_contract.conf``. Rust
resolves it at compile time and Python at import time, so a second declaration
would let the two runtimes drift apart again.

The scan is intentionally narrow: it walks code and config files only, strips
line comments and Python triple-quoted docstrings, and treats an occurrence of
the identifier followed by ``=`` or ``:`` and a numeric literal as a
declaration. Markdown and the checker itself are never scanned.

Usage::

    python3 scripts/check_contract_single_source.py --root .
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

KEY = "SAFE_BASELINE_TTL_SECONDS"
CONTRACT_RELATIVE = Path("contracts") / "policy_contract.conf"

SCANNED_SUFFIXES = {
    ".conf",
    ".cfg",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".env",
    ".rs",
    ".py",
    ".sh",
}

SKIPPED_DIRS = {
    ".git",
    "target",
    "node_modules",
    ".worktrees",
    "openspec",
    "docs",
    ".sdlc",
}

# Generic envelope defaults that are deliberately NOT safe-baseline declarations.
# They are bare ``900`` values inside these functions and never mention the key.
EXEMPT_DEFAULTS = (
    ("backend/core/schemas.py", "from_dict", 900),
    ("backend/core/schemas.py", "default_active", 900),
)

_DECLARATION_RE = re.compile(r"\b" + KEY + r"\b\s*[:=]\s*(\d+)\b")
_DOCSTRING_RE = re.compile(
    r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'',
    re.MULTILINE,
)


def _strip_comments(text: str) -> str:
    """Remove Python docstrings and ``#`` / ``//`` line comments."""
    text = _DOCSTRING_RE.sub("", text)
    cleaned_lines = []
    for line in text.splitlines():
        for marker in ("//", "#"):
            index = line.find(marker)
            if index != -1:
                line = line[:index]
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _iter_scanned_files(root: Path):
    checker = Path(__file__).resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped trees in place: `rglob` would descend into sibling
        # worktrees, generated targets, documentation examples, and the
        # OpenSpec change tree, where contract copies are not declarations.
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRS)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix not in SCANNED_SUFFIXES:
                continue
            try:
                if path.resolve() == checker:
                    continue
            except OSError:
                pass
            yield path


def _declarations(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in _iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # pragma: no cover - unreadable file is an error
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            raise
        if _DECLARATION_RE.search(_strip_comments(text)):
            found.append(path)
    return found


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the policy contract key is declared exactly once."
    )
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    expected = (root / CONTRACT_RELATIVE).resolve()

    if not expected.exists():
        print(
            f"error: missing contract file {CONTRACT_RELATIVE.as_posix()} under {root}",
            file=sys.stderr,
        )
        return 1

    declarations = [path.resolve() for path in _declarations(root)]

    if expected not in declarations:
        print(
            f"error: {CONTRACT_RELATIVE.as_posix()} does not declare {KEY}",
            file=sys.stderr,
        )
        return 1

    duplicates = [path for path in declarations if path != expected]
    if duplicates:
        for path in duplicates:
            print(
                f"error: duplicate {KEY} declaration in {_relative(root, path)}",
                file=sys.stderr,
            )
        return 1

    print(f"contract single source: OK ({_relative(root, expected)})")
    print(f"  declaration: {KEY} in {_relative(root, expected)}")
    print("  EXEMPT_DEFAULTS (generic envelope defaults, not safe-baseline declarations):")
    for relative, function, value in EXEMPT_DEFAULTS:
        print(f"    {relative}::{function} ({value})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
