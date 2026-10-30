"""Single provenance vocabulary for performance metrics and Palace drawers.

Every number the warm path serves is either derived from an attributed
population or absent. This module owns the two closed enums, the mapping from
an execution population to the provenance of its rows, and the fail-closed
normalisers shared by the state store, the hierarchy, the Palace, and the API.

No third-party dependency: the module is importable from the hot warm-path
modules without pulling anything beyond the standard library.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Performance payload provenance (spec: "Every performance payload declares
# its provenance").
METRIC_SOURCES = ("MEASURED", "SIMULATED", "FIXTURE", "BOOTSTRAP")

# Canonical machine-readable kind for the deterministic execution artefact.
# The fixture is a rule and plumbing sanity check, not a fill simulation; a real
# event-driven replay remains issue #3.
ARTIFACT_KIND_POLICY_SANITY_CHECK = "policy_sanity_check"

# Palace drawer provenance (spec: "Palace drawers declare provenance").
DRAWER_SOURCES = ("LLM", "DETERMINISTIC_FALLBACK", "BOOTSTRAP")

# Population token -> provenance of every row produced by that population.
# The per-leaf backtest token is deliberately absent: a per-leaf replay is the same
# deterministic fixture population, not a fourth vocabulary.
EXECUTIONS_SOURCE_TO_METRIC_SOURCE: Dict[str, str] = {
    "backtest_fixture": METRIC_SOURCES[2],  # FIXTURE
    "paper_model": METRIC_SOURCES[1],  # SIMULATED
    "live_testnet": METRIC_SOURCES[0],  # MEASURED
}

BOOTSTRAP_DRAWER_SOURCE = DRAWER_SOURCES[2]


def execution_rows_source(executions_source: Optional[str]) -> Optional[str]:
    """Map an ``executions_source`` population token to the row provenance.

    Unknown or absent tokens resolve to ``None`` (fail-closed): a consumer must
    render the value as unattributed rather than promote it to a known source.
    """
    if executions_source is None:
        return None
    return EXECUTIONS_SOURCE_TO_METRIC_SOURCE.get(str(executions_source))


def eligible_drawer_source(source: Optional[str]) -> bool:
    """Only a real reasoning call is eligible for continuity injection."""
    return source in (DRAWER_SOURCES[0], DRAWER_SOURCES[1])


def normalise_metric_source(source: Optional[str]) -> Optional[str]:
    """Return the metric source unchanged when known, otherwise ``None``."""
    return source if source in METRIC_SOURCES else None


def normalise_drawer_source(source: Optional[str]) -> str:
    """Fail closed: a missing or unknown drawer source is ``BOOTSTRAP``."""
    return source if source in DRAWER_SOURCES else BOOTSTRAP_DRAWER_SOURCE


def normalise_drawer_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce a drawer payload to its provenance-consistent telemetry.

    A legacy drawer (no ``source``) or any drawer labelled ``BOOTSTRAP`` must
    not claim a model, a token count, a cost, or a prior confirmation. The
    function mutates and returns ``payload``.

    Normalisation is applied in memory only: the append-only JSONL audit trail
    keeps its original bytes.
    """
    source = normalise_drawer_source(payload.get("source"))
    payload["source"] = source
    if source == BOOTSTRAP_DRAWER_SOURCE:
        payload["model_used"] = ""
        payload["tokens_used"] = 0
        payload["cost_usd"] = 0.0
        payload["thesis_continuity"] = "INITIAL"
    return payload
