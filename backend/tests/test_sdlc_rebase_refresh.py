"""Regression tests for the SDLC mechanical-rebase path.

A rebase rewrites the branch SHA, so the DEV gate no longer recognises the
reviewed commit. `sdlc.py refresh-sha` re-anchors the reviewed SHA without
spending a review round, but only when the change itself did not move. These
tests pin both sides of that decision: a faithful rebase is accepted, a rebase
that smuggled a content change is refused.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "sdlc"))

import sdlc  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo, text=True, capture_output=True, check=True
    )
    return proc.stdout


class MechanicalRebaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        _git(self.repo, "init", "-q", "-b", "master")
        _git(self.repo, "config", "user.email", "test@example.com")
        _git(self.repo, "config", "user.name", "test")
        _git(self.repo, "config", "commit.gpgsign", "false")
        (self.repo / "a.txt").write_text("base\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "base")
        self.base = self._head()
        _git(self.repo, "update-ref", "refs/remotes/origin/master", self.base)
        _git(self.repo, "checkout", "-qb", "feature")
        (self.repo / "leaf.py").write_text("LEAF = 1\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "feat: add leaf [demo-change]")
        self.old = self._head()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _head(self) -> str:
        return _git(self.repo, "rev-parse", "HEAD").strip()

    def _advance_master(self, filename: str) -> None:
        _git(self.repo, "checkout", "-q", "master")
        (self.repo / filename).write_text("other\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", f"other change {filename}")
        _git(self.repo, "update-ref", "refs/remotes/origin/master", self._head())

    def test_faithful_rebase_is_accepted(self) -> None:
        self._advance_master("b.txt")
        _git(self.repo, "checkout", "-q", "feature")
        _git(self.repo, "rebase", "-q", "master")
        new = self._head()
        self.assertNotEqual(new, self.old)
        self.assertTrue(
            sdlc._mechanical_rebase_ok(
                self.old, new, self.repo, self.base, "demo-change"
            )
        )

    def test_rebase_with_content_change_is_refused(self) -> None:
        self._advance_master("c.txt")
        _git(self.repo, "checkout", "-q", "feature")
        _git(self.repo, "rebase", "-q", "master")
        (self.repo / "leaf.py").write_text("LEAF = 2\n")
        _git(self.repo, "commit", "-qam", "feat: change leaf [demo-change]")
        new = self._head()
        self.assertFalse(
            sdlc._mechanical_rebase_ok(
                self.old, new, self.repo, self.base, "demo-change"
            )
        )

    def test_merged_master_is_accepted(self) -> None:
        """The other accepted shape: master merged into the branch."""
        self._advance_master("d.txt")
        _git(self.repo, "checkout", "-q", "feature")
        _git(self.repo, "merge", "-q", "--no-edit", "master")
        new = self._head()
        self.assertTrue(
            sdlc._mechanical_rebase_ok(
                self.old, new, self.repo, self.base, "demo-change"
            )
        )

    def test_missing_base_is_refused(self) -> None:
        self._advance_master("e.txt")
        _git(self.repo, "checkout", "-q", "feature")
        _git(self.repo, "rebase", "-q", "master")
        new = self._head()
        self.assertFalse(
            sdlc._mechanical_rebase_ok(self.old, new, self.repo, "", "demo-change")
        )


class ContextPackTest(unittest.TestCase):
    def test_invariants_are_derived_from_config(self) -> None:
        text = sdlc._invariants_from_config()
        self.assertIn("- ", text)
        self.assertNotIn("See `openspec/config.yaml`", text)
        self.assertIn("HardRiskGate", text)


if __name__ == "__main__":
    unittest.main()
