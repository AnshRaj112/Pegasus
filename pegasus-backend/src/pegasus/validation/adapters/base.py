# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T07:03:36Z
# --- END GENERATED FILE METADATA ---

"""Tabular source adapter contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Protocol


@dataclass(slots=True)
class TabularColumn:
    name: str
    data_type: str = "string"
    nullable: bool = True


@dataclass(slots=True)
class TabularSchema:
    columns: list[TabularColumn] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


class TabularSourceAdapter(Protocol):
    path: Path

    def get_schema(self) -> TabularSchema: ...

    def get_row_count(self) -> int | None: ...

    def stream_records(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]: ...
