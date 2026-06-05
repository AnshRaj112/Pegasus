# --- BEGIN GENERATED FILE METADATA ---
<<<<<<< HEAD
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
=======
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
>>>>>>> 94051c3720b8bad458bdf77183420f7b053658d8
# --- END GENERATED FILE METADATA ---

"""Plugin registry for future/custom format detection extensions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pegasus.validation.file_detection.types import DetectionStage

_FormatPlugin = Callable[[list[tuple[str, int, str]]], "DetectionStage | None"]

_PLUGINS: list[_FormatPlugin] = []


def register_format_plugin(fn: _FormatPlugin) -> _FormatPlugin:
    """Register a plugin that may override candidate format selection."""
    _PLUGINS.append(fn)
    return fn


def apply_format_plugins(candidates: list[tuple[str, int, str]]) -> "DetectionStage | None":
    from pegasus.validation.file_detection.types import DetectionStage

    for plugin in _PLUGINS:
        result = plugin(list(candidates))
        if result is not None:
            return result
    return None
