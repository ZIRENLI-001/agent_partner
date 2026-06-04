from __future__ import annotations

from copy import deepcopy

from backend.evaluation_engine.app import DEMO_CONTEXT


def get_current_context() -> dict[str, object]:
    return deepcopy(DEMO_CONTEXT)
