"""Plugin registry for custom / future file formats."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

DetectFn = Callable[[FileSample], DetectionStageResult | None]


class FormatPlugin(Protocol):
    """Extension point for new formats without editing core layers."""

    name: str
    extensions: frozenset[str]
    magic_types: frozenset[str]

    def detect(self, sample: FileSample) -> DetectionStageResult | None:
        """Optional extra detection from a sample window."""

    def suggested_file_format(self) -> str:
        """Token passed to validation routing (``csv``, ``parquet``, etc.)."""


@dataclass(slots=True)
class RegisteredFormatPlugin:
    name: str
    extensions: frozenset[str]
    magic_types: frozenset[str] = field(default_factory=frozenset)
    detect_fn: DetectFn | None = None
    file_format_token: str = ""

    def detect(self, sample: FileSample) -> DetectionStageResult | None:
        if self.detect_fn is None:
            return None
        return self.detect_fn(sample)

    def suggested_file_format(self) -> str:
        return self.file_format_token or self.name


_PLUGINS: dict[str, RegisteredFormatPlugin] = {}


def register_format_plugin(plugin: RegisteredFormatPlugin, *, replace: bool = False) -> None:
    if plugin.name in _PLUGINS and not replace:
        raise ValueError(f"format plugin {plugin.name!r} already registered")
    _PLUGINS[plugin.name] = plugin


def get_format_plugin(name: str) -> RegisteredFormatPlugin | None:
    return _PLUGINS.get(name)


def list_format_plugins() -> list[str]:
    return sorted(_PLUGINS.keys())


def detect_with_plugins(sample: FileSample) -> DetectionStageResult | None:
    ext = sample.suffix
    for plugin in _PLUGINS.values():
        if ext and ext in plugin.extensions:
            hit = plugin.detect(sample)
            if hit is not None:
                return hit
    return None


def plugin_for_magic_type(magic_type: str) -> RegisteredFormatPlugin | None:
    for plugin in _PLUGINS.values():
        if magic_type in plugin.magic_types:
            return plugin
    return None


def _register_builtins() -> None:
    builtins = (
        RegisteredFormatPlugin("parquet", frozenset({".parquet"}), magic_types=frozenset({"parquet"}), file_format_token="parquet"),
        RegisteredFormatPlugin("orc", frozenset({".orc"}), magic_types=frozenset({"orc"}), file_format_token="orc"),
        RegisteredFormatPlugin("avro", frozenset({".avro"}), magic_types=frozenset({"avro"}), file_format_token="avro"),
        RegisteredFormatPlugin(
            "excel",
            frozenset({".xlsx", ".xls"}),
            magic_types=frozenset({"ole_compound", "excel"}),
            file_format_token="excel",
        ),
    )
    for p in builtins:
        if p.name not in _PLUGINS:
            register_format_plugin(p)


_register_builtins()
