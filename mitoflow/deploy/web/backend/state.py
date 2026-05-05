"""Shared runtime state for the MitoFlow web backend."""

from __future__ import annotations

from typing import Any, Dict, Optional


class AppState:
    """Mutable application state shared across route modules."""

    ai_service: Optional[Any] = None
    ai_sessions: Dict[str, float] = {}
    ai_store: Optional[Any] = None
    tasks: Dict[str, Any] = {}
    session_meta: Dict[str, Any] = {}


state = AppState()
