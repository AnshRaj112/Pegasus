"""Pluggable format detection and validation handlers."""

from pegasus.validation.file_detection.plugins.registry import (
    FormatPlugin,
    get_format_plugin,
    list_format_plugins,
    register_format_plugin,
)

__all__ = [
    "FormatPlugin",
    "get_format_plugin",
    "list_format_plugins",
    "register_format_plugin",
]
