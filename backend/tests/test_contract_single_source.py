"""The safe-baseline TTL must be declared exactly once.

Runs `scripts/check_contract_single_source.py` against the real repository and
against temporary trees that exercise the duplicate, comment, docstring, and
exemption rules.
"""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.core.schemas import SAFE_BASELINE_TTL_SECONDS, PolicyEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "check_contract_single_source.py"
CONTRACT = REPO_ROOT / "contracts" / "policy_contract.conf"
KEY = "SAFE_BASELINE_TTL_SECONDS"


def _load_checker():
    spec = importlib.util.spec_from_file_location("contract_single_source", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestContractSingleSource(unittest.TestCase):
    def test_repository_declares_the_contract_once(self) -> None:
        checker = _load_checker()
        self.assertEqual(checker.main(["--root", str(REPO_ROOT)]), 0)

    def test_duplicate_declaration_is_rejected(self) -> None:
        checker = _load_checker()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contracts").mkdir()
            shutil.copy(CONTRACT, root / "contracts" / "policy_contract.conf")
            (root / "duplicate.conf").write_text(f"{KEY}=900\n", encoding="utf-8")

            self.assertEqual(checker.main(["--root", str(root)]), 1)

    def test_comments_and_docstrings_are_not_declarations(self) -> None:
        checker = _load_checker()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "contracts").mkdir()
            shutil.copy(CONTRACT, root / "contracts" / "policy_contract.conf")
            schemas_dir = root / "backend" / "core"
            schemas_dir.mkdir(parents=True)
            schemas_dir.joinpath("schemas.py").write_text(
                '"""Fixture: '
                + f"{KEY}=900"
                + ' is documentation, not a declaration."""\n\n'
                "def from_dict(data):\n"
                f"    # {KEY}=900 in a comment must not be flagged.\n"
                '    return {"ttl_seconds": 900}\n\n'
                "def default_active():\n"
                '    return {"ttl_seconds": 900}\n',
                encoding="utf-8",
            )

            self.assertEqual(checker.main(["--root", str(root)]), 0)

    def test_exempt_defaults_still_equal_the_contract_value(self) -> None:
        checker = _load_checker()
        declared = None
        for line in CONTRACT.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key.strip() == KEY:
                declared = int(value.strip())

        self.assertIsNotNone(declared)
        for _, _, value in checker.EXEMPT_DEFAULTS:
            self.assertEqual(value, declared)

    def test_python_baseline_resolves_the_named_key(self) -> None:
        self.assertEqual(SAFE_BASELINE_TTL_SECONDS, 900)
        self.assertEqual(
            PolicyEnvelope.safe_baseline(now_ms=0).ttl_seconds,
            SAFE_BASELINE_TTL_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
