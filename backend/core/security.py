"""Control plane security and CORS configuration helpers."""

from __future__ import annotations

import hmac
import os
from typing import List, Optional, Tuple


def resolve_cors_config(env_val: Optional[str] = None) -> Tuple[List[str], bool]:
    """Parse CORS_ALLOWED_ORIGINS per the Fetch specification.

    When wildcard '*' is among the allowed origins (or when the variable is unset/empty),
    allow_credentials MUST be False. When only explicit origins are provided,
    allow_credentials MUST be True.
    """
    if env_val is None:
        env_val = os.getenv("CORS_ALLOWED_ORIGINS")
    raw = env_val.strip() if env_val else ""
    if not raw:
        return ["*"], False
    origins = [orig.strip() for orig in raw.split(",") if orig.strip()]
    if not origins or "*" in origins:
        return origins if origins else ["*"], False
    return origins, True


def verify_bearer_token(auth_header: Optional[str], expected_token: str) -> bool:
    """Verify Authorization Bearer token using constant-time comparison."""
    if not expected_token:
        return True
    if not auth_header:
        return False
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        return False
    return hmac.compare_digest(parts[1], expected_token)
