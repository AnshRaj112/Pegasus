"""Row pairing for unsorted fixed-width files (exact + fuzzy join keys)."""

from __future__ import annotations

from difflib import SequenceMatcher


def join_key_similarity(left: str, right: str) -> float:
    """Score how likely two join-key values refer to the same row."""
    a = left.strip().lower()
    b = right.strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    # Typos with rearranged characters (abc vs bca) should pair, not split missing/extra.
    if len(a) == len(b) and sorted(a) == sorted(b):
        ratio = max(ratio, 0.9)
    # Small edit distance on short keys (single-character typos).
    if len(a) == len(b) and len(a) <= 32:
        edits = sum(1 for x, y in zip(a, b, strict=True) if x != y)
        if edits == 1:
            ratio = max(ratio, 0.88)
    return ratio


def fuzzy_pair_by_join_key(
    source_rows: list[tuple[int, str, str]],
    target_rows: list[tuple[int, str, str]],
    *,
    threshold: float,
) -> tuple[list[tuple[tuple[int, str, str], tuple[int, str, str], float]], list[tuple[int, str, str]], list[tuple[int, str, str]]]:
    """Greedy one-to-one pairing on join-key similarity.

    Each item is ``(line_index, line_text, join_key_value)``.
    Returns ``(pairs, unmatched_source, unmatched_target)``.
    """
    if not source_rows or not target_rows:
        return [], list(source_rows), list(target_rows)

    candidates: list[tuple[float, int, int]] = []
    for si, (_, _, s_key) in enumerate(source_rows):
        for ti, (_, _, t_key) in enumerate(target_rows):
            score = join_key_similarity(s_key, t_key)
            if score >= threshold and s_key.strip() != t_key.strip():
                candidates.append((score, si, ti))
            elif score >= threshold and s_key.strip() == t_key.strip():
                # Exact keys should have been handled earlier; skip.
                continue

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_src: set[int] = set()
    used_tgt: set[int] = set()
    pairs: list[tuple[tuple[int, str, str], tuple[int, str, str], float]] = []

    for score, si, ti in candidates:
        if si in used_src or ti in used_tgt:
            continue
        used_src.add(si)
        used_tgt.add(ti)
        pairs.append((source_rows[si], target_rows[ti], score))

    unmatched_src = [row for i, row in enumerate(source_rows) if i not in used_src]
    unmatched_tgt = [row for i, row in enumerate(target_rows) if i not in used_tgt]
    return pairs, unmatched_src, unmatched_tgt
