#!/usr/bin/env python3
"""Shared helpers for the Robotrader SDLC tooling.

No third-party dependencies. Python 3.10+.
"""

from __future__ import annotations

try:
    import fcntl
except ImportError:  # Windows: advisory locking is unavailable; state writes stay atomic.
    fcntl = None  # type: ignore[assignment]

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
SDLC_DIR = REPO_ROOT / "sdlc"
RUNTIME_ROOT = REPO_ROOT / ".sdlc"
OPENSPEC_CHANGES = REPO_ROOT / "openspec" / "changes"

DEFAULTS = {
    "SDLC_CLI": "auto",
    "SDLC_MAX_ROUNDS": "3",
    "SDLC_MAX_PARALLEL": "3",
    "SDLC_BASE_BRANCH": "master",
    "SDLC_HUMAN_GATES": "merge",
    "SDLC_CLAUDE_PERMISSION_MODE": "auto",
    "SDLC_AGY_MODEL": "gemini-3.8-flash-medium",
    "SDLC_AGY_MODE": "",
    "SDLC_AGY_DANGEROUSLY_SKIP_PERMISSIONS": "false",
    "SDLC_AGY_USE_DEFAULT_AGENT": "false",
    "SDLC_AUTO_MERGE": "false",
}

CHANGE_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STAGE_ROLES = {
    "spec": ("sdlc-spec-author", "sdlc-spec-reviewer"),
    "plan": ("sdlc-plan-author", "sdlc-plan-reviewer"),
    "dev": ("sdlc-dev", "sdlc-dev-reviewer"),
}
LANE_STAGES = {
    "M": ("dev",),
    "S": ("spec", "dev"),
    "L": ("spec", "plan", "dev"),
}


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

def log(message: str) -> None:
    print(f"[sdlc] {message}")


def warn(message: str) -> None:
    print(f"[sdlc] warning: {message}", file=sys.stderr)


def die(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"[sdlc] error: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def load_config() -> dict[str, str]:
    cfg = dict(DEFAULTS)
    path = SDLC_DIR / "config.env"
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            cfg[key.strip()] = value.strip().strip('"').strip("'")
    for key in list(cfg):
        if os.environ.get(key):
            cfg[key] = os.environ[key]
    return cfg


def cfg_int(cfg: dict[str, str], key: str) -> int:
    try:
        return int(cfg.get(key, DEFAULTS[key]))
    except (TypeError, ValueError):
        die(f"{key} must be an integer, got {cfg.get(key)!r}")


def cfg_bool(cfg: dict[str, str], key: str) -> bool:
    return str(cfg.get(key, DEFAULTS[key])).strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Time, paths, text
# --------------------------------------------------------------------------- #

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)[:60] or "change"


def validate_change_id(change_id: str) -> None:
    if not CHANGE_ID_RE.match(change_id):
        die(f"invalid change id {change_id!r}: use kebab-case (a-z, 0-9, '-')")


def main_repo_root() -> Path:
    """Return the main checkout root, even when called from a linked worktree."""
    try:
        proc = run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return Path(proc.stdout.strip()).resolve().parent
    except OSError:
        pass
    proc = run(["git", "rev-parse", "--git-common-dir"], check=False)
    if proc.returncode == 0 and proc.stdout.strip():
        candidate = Path(proc.stdout.strip())
        if not candidate.is_absolute():
            candidate = (REPO_ROOT / candidate).resolve()
        return candidate.parent
    return REPO_ROOT


def _candidate_runtime_dirs(change_id: str) -> list[Path]:
    candidates = [RUNTIME_ROOT / change_id]
    main = main_repo_root()
    candidates.append(main / ".sdlc" / change_id)
    worktrees = main / ".worktrees"
    if worktrees.exists():
        for path in sorted(worktrees.glob(f"*/.sdlc/{change_id}")):
            candidates.append(path)
    return candidates


def runtime_dir(change_id: str) -> Path:
    for candidate in _candidate_runtime_dirs(change_id):
        if (candidate / "state.json").exists():
            return candidate
    return RUNTIME_ROOT / change_id


def list_runtime_dirs() -> list[Path]:
    found: dict[Path, None] = {}
    roots = [RUNTIME_ROOT, main_repo_root() / ".sdlc"]
    worktrees = main_repo_root() / ".worktrees"
    if worktrees.exists():
        roots.extend(worktrees.glob("*/.sdlc"))
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*/state.json"):
            found[path.parent] = None
    return sorted(found)


def state_path(change_id: str) -> Path:
    return runtime_dir(change_id) / "state.json"


def openspec_change_dir(change_id: str) -> Path:
    candidates = [OPENSPEC_CHANGES / change_id]
    main = main_repo_root()
    candidates.append(main / "openspec" / "changes" / change_id)
    worktrees = main / ".worktrees"
    if worktrees.exists():
        for path in sorted(worktrees.glob(f"*/openspec/changes/{change_id}")):
            candidates.append(path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return OPENSPEC_CHANGES / change_id


def ensure_runtime_dirs(change_id: str) -> None:
    root = runtime_dir(change_id)
    for sub in ("reviews", "revisions", "evidence", "briefs"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

@contextmanager
def _state_lock(change_id: str):
    root = runtime_dir(change_id)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".state.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_state(change_id: str) -> dict[str, Any]:
    path = state_path(change_id)
    if not path.exists():
        die(f"no state for change {change_id!r} ({path})")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(change_id: str, state: dict[str, Any]) -> None:
    ensure_runtime_dirs(change_id)
    path = state_path(change_id)
    with _state_lock(change_id):
        fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".state.", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


def new_state(
    *,
    change_id: str,
    title: str,
    issue: int,
    lane: str,
    reason: str,
    branch: str,
    worktree: str,
    base_branch: str,
    base_sha: str,
    areas: Iterable[str],
    human_gates: Iterable[str],
) -> dict[str, Any]:
    stages: dict[str, dict[str, Any]] = {}
    for stage in ("spec", "plan", "dev"):
        required = stage in LANE_STAGES[lane]
        stages[stage] = {
            "status": "pending" if required else "skipped",
            "rounds": 0,
            "last_verdict": None,
            "last_reviewer": None,
            "last_sha": None,
            "updated_at": None,
        }
    return {
        "version": 1,
        "change_id": change_id,
        "title": title,
        "issue": issue,
        "lane": lane,
        "lane_reason": reason,
        "lane_change": None,
        "branch": branch,
        "worktree": worktree,
        "base_branch": base_branch,
        "base_sha": base_sha,
        "created_at": now_iso(),
        "human_gates": list(human_gates),
        "status": "triage",
        "pr": None,
        "areas": list(areas),
        "stages": stages,
        "escalation": None,
    }


def required_stages(state: dict[str, Any]) -> tuple[str, ...]:
    return LANE_STAGES[state["lane"]]


def stage_is_approved(state: dict[str, Any], stage: str) -> bool:
    data = state["stages"].get(stage, {})
    return data.get("status") == "approved"


# --------------------------------------------------------------------------- #
# Verdicts
# --------------------------------------------------------------------------- #

def verdict_files(change_id: str, stage: str | None = None) -> list[Path]:
    root = runtime_dir(change_id) / "reviews"
    if not root.exists():
        return []
    pattern = f"{stage}-r*.md" if stage else "*-r*.md"
    return sorted(root.glob(pattern), key=lambda p: (p.name.split("-r")[0], int(re.search(r"-r(\d+)", p.name).group(1))))


def read_json_block(text: str, marker: str = "## Machine Verdict") -> dict[str, Any]:
    """Extract the first fenced JSON block after the marker."""
    index = text.find(marker)
    if index == -1:
        raise ValueError(f"missing marker {marker!r}")
    tail = text[index:]
    match = re.search(r"```json\s*\n(.*?)\n```", tail, re.DOTALL)
    if not match:
        raise ValueError("missing fenced ```json block after marker")
    return json.loads(match.group(1))


def load_verdict(path: Path) -> dict[str, Any]:
    return read_json_block(read_text(path))


def latest_verdict_path(change_id: str, stage: str) -> Path | None:
    files = verdict_files(change_id, stage)
    return files[-1] if files else None


def latest_verdict(change_id: str, stage: str) -> dict[str, Any] | None:
    path = latest_verdict_path(change_id, stage)
    return load_verdict(path) if path else None


def open_blocking(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        f
        for f in findings
        if f.get("status") == "open" and f.get("severity") in {"blocker", "major"}
    ]


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #

def run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        text=True,
        capture_output=capture,
        env={**os.environ, **(env or {})},
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        die(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{detail}")
    return proc


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def gh_available() -> bool:
    return have("gh")


def openspec_available() -> bool:
    return have("openspec")


def gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    if not gh_available():
        die("gh CLI is required for issue and PR operations")
    return run(["gh", *args], check=check)


def issue_comment(issue: int, body: str) -> None:
    if issue <= 0:
        warn("no issue recorded; comment skipped")
        return
    if not gh_available():
        warn("gh not available; comment skipped")
        return
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(body)
        tmp = handle.name
    try:
        gh(["issue", "comment", str(issue), "--body-file", tmp])
    finally:
        os.unlink(tmp)


def ensure_labels(labels: Iterable[str]) -> None:
    if not gh_available():
        return
    listed = gh(["label", "list", "--limit", "200", "--json", "name"], check=False)
    existing: set[str] = set()
    if listed.returncode == 0:
        try:
            existing = {item["name"] for item in json.loads(listed.stdout)}
        except (json.JSONDecodeError, KeyError):
            existing = set()
    colors = {
        "sdlc": "5319E7",
        "sdlc:lane-m": "0E8A16",
        "sdlc:lane-s": "FBCA04",
        "sdlc:lane-l": "D93F0B",
        "sdlc:escalated": "B60205",
    }
    for label in labels:
        if label in existing:
            continue
        color = colors.get(label, "1D76DB")
        gh(
            ["label", "create", label, "--color", color, "--description", "Robotrader SDLC"],
            check=False,
        )


def event_marker(event: dict[str, Any]) -> str:
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"<!-- sdlc:event {payload} -->"


def stage_from_status(status: str) -> str:
    for suffix in ("-review",):
        if status.endswith(suffix):
            return status[: -len(suffix)]
    return status
