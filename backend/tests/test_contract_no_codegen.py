"""The PolicyEnvelope contract stays hand-maintained: no codegen may sneak in.

Drift is detected by the cross-language round-trip test, not by generated
schema artifacts or a build step. This guard keeps that decision honest.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_CODEGEN = re.compile(
    r"schemars|progenitor|datamodel-codegen|json-schema|codegen",
    re.IGNORECASE,
)

# Unrelated build scripts that are explicitly allowed to exist without
# generating contract source.
ALLOWED_BUILD_SCRIPTS: set = set()


def _manifests():
    yield REPO_ROOT / "engine-rs" / "Cargo.toml"
    yield from sorted((REPO_ROOT / "engine-rs" / "crates").glob("*/Cargo.toml"))
    yield REPO_ROOT / "backend" / "pyproject.toml"
    lock = REPO_ROOT / "backend" / "poetry.lock"
    if lock.exists():
        yield lock


def _generated_contract_files():
    for base in (
        REPO_ROOT / "engine-rs",
        REPO_ROOT / "backend",
        REPO_ROOT / "contracts",
    ):
        for path in base.rglob("*"):
            if not path.is_file() or "target" in path.parts:
                continue
            name = path.name.lower()
            if name.endswith(".gen.rs") or name.endswith(".gen.py"):
                yield path
            elif "generated" in name and "schema" in name:
                yield path


class TestNoContractCodegen(unittest.TestCase):
    def test_no_schema_codegen_dependency_in_manifests(self) -> None:
        for manifest in _manifests():
            self.assertTrue(manifest.exists(), f"missing manifest: {manifest}")
            match = FORBIDDEN_CODEGEN.search(manifest.read_text(encoding="utf-8"))
            if match is not None:
                self.fail(
                    f"schema codegen token {match.group(0)!r} found in {manifest}"
                )

    def test_no_generated_contract_file_is_tracked(self) -> None:
        generated = [path for path in _generated_contract_files()]
        self.assertEqual(generated, [])

    def test_no_build_script_emits_contract_source(self) -> None:
        for build_script in (REPO_ROOT / "engine-rs").rglob("build.rs"):
            relative = build_script.relative_to(REPO_ROOT).as_posix()
            if relative in ALLOWED_BUILD_SCRIPTS:
                continue
            text = build_script.read_text(encoding="utf-8").lower()
            self.assertNotIn("policy_contract", text, relative)
            self.assertNotIn("contracts/", text, relative)


if __name__ == "__main__":
    unittest.main()
