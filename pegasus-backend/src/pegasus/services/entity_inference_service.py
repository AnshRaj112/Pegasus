# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T13:34:40Z
# --- END GENERATED FILE METADATA ---

"""Inference helpers for deriving an entity from source/target filenames."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_STOP_TOKENS = {"source", "target", "src", "tgt", "file", "final", "raw", "data"}


@dataclass(slots=True)
class EntityDefinition:
    name: str
    display_name: str
    aliases: list[str]


@dataclass(slots=True)
class EntityInferenceResult:
    inferred_entity: str
    display_name: str
    confidence: str
    matched_existing: bool
    candidate_tokens: list[str]
    source_tokens: list[str]
    target_tokens: list[str]


def _normalize_entity_name(value: str) -> str:
    normalized = "_".join([t for t in _TOKEN_SPLIT_RE.split(value.lower()) if t])
    return normalized.strip("_")


def normalize_entity_name(value: str) -> str:
    return _normalize_entity_name(value)


def _tokenize_filename(filename: str | None) -> list[str]:
    if not filename:
        return []
    stem = Path(filename).stem.lower()
    tokens = [t for t in _TOKEN_SPLIT_RE.split(stem) if t]
    filtered: list[str] = []
    for token in tokens:
        if token in _STOP_TOKENS:
            continue
        if token.isdigit() and len(token) in {6, 8, 10, 12, 14}:
            continue
        filtered.append(token)
    return filtered


def infer_entity_from_filenames(
    source_filename: str | None,
    target_filename: str | None,
    entities: list[EntityDefinition],
) -> EntityInferenceResult:
    source_tokens = _tokenize_filename(source_filename)
    target_tokens = _tokenize_filename(target_filename)
    source_set, target_set = set(source_tokens), set(target_tokens)
    shared_tokens = [token for token in source_tokens if token in target_set]
    combined_tokens = shared_tokens or source_tokens or target_tokens

    best: EntityDefinition | None = None
    best_score = -1
    for entity in entities:
        alias_tokens: set[str] = set()
        for alias in [entity.name, *entity.aliases]:
            alias_tokens.update([t for t in _TOKEN_SPLIT_RE.split(alias.lower()) if t])
        score = len((source_set | target_set) & alias_tokens)
        if score > best_score:
            best_score = score
            best = entity

    if best is not None and best_score > 0:
        return EntityInferenceResult(
            inferred_entity=best.name,
            display_name=best.display_name,
            confidence="high" if best_score >= 2 else "medium",
            matched_existing=True,
            candidate_tokens=combined_tokens,
            source_tokens=source_tokens,
            target_tokens=target_tokens,
        )

    fallback = combined_tokens[0] if combined_tokens else "unknown_entity"
    normalized = _normalize_entity_name(fallback) or "unknown_entity"
    return EntityInferenceResult(
        inferred_entity=normalized,
        display_name=normalized.replace("_", " ").title(),
        confidence="low",
        matched_existing=False,
        candidate_tokens=combined_tokens,
        source_tokens=source_tokens,
        target_tokens=target_tokens,
    )
