"""Typed errors shared by the warm path and the HTTP control plane.

This module stays dependency-light: it imports no web framework at module scope,
so ``backend.core.state_store`` can raise the typed error without pulling
FastAPI into the request-path core. The exception handler lazy-imports
``JSONResponse`` only when it builds a response.
"""

from __future__ import annotations

from typing import Sequence

ROBOTRADER_NODE_BUILD_COMMAND = (
    "cargo build --release --manifest-path engine-rs/Cargo.toml --bin robotrader-node"
)


class RustBinaryNotFoundError(RuntimeError):
    """No ``robotrader-node`` binary is available and no compiler fallback exists.

    ``candidate_paths`` is the debug/release pair the resolver searched, in
    precedence order. The rendered ``detail`` names both candidates and the
    exact root-runnable build command so an operator can act on it directly.
    """

    def __init__(self, candidate_paths: Sequence[object]) -> None:
        self.candidate_paths = tuple(str(path) for path in candidate_paths)
        debug_path = self.candidate_paths[0]
        release_path = self.candidate_paths[-1]
        self.detail = (
            "robotrader-node binary not found. "
            f"Checked debug candidate {debug_path} and release candidate {release_path}. "
            f"Build it from the repository root with: {ROBOTRADER_NODE_BUILD_COMMAND}"
        )
        super().__init__(self.detail)


async def rust_binary_not_found_handler(request: object, exc: RustBinaryNotFoundError) -> object:
    """Return the uniform HTTP 503 payload for a missing engine binary."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": exc.detail})
