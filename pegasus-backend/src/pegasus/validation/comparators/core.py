# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:59:50Z
# --- END GENERATED FILE METADATA ---

"""Token-minimal source/target row validation core."""
from __future__ import annotations

import ast
import json
import re
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

_C = (list, dict, tuple)
_DF = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
)
_N = frozenset({"", "null", "none", "na", "n/a"})
_DIGITS = re.compile(r"\D+")
_SQL_REGEXP_REPLACE = re.compile(
    r"REGEXP_REPLACE\s*\([^,]+,\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'",
    re.IGNORECASE,
)


def resolve_regex_transform(pattern: str | None, replacement: str = "") -> tuple[str, str] | None:
    """Return (pattern, replacement) from a plain regex or SQL REGEXP_REPLACE expression."""
    if not pattern or not pattern.strip():
        return None
    text = pattern.strip()
    match = _SQL_REGEXP_REPLACE.search(text)
    if match:
        return match.group(1), match.group(2)
    return text, replacement


def apply_value_transform(
    value: Any,
    *,
    pattern: str | None = None,
    replacement: str = "",
    strip_prefix: str | None = None,
) -> Any:
    if value is None:
        return value
    text = str(value)
    if strip_prefix and text.startswith(strip_prefix):
        text = text[len(strip_prefix) :]
    resolved = resolve_regex_transform(pattern, replacement)
    if resolved:
        pat, repl = resolved
        text = re.sub(pat, repl, text)
    return text


def _idx(header: Sequence[str] | None, col: Any) -> int:
    if isinstance(col, int):
        return col
    if header is not None and col in header:
        return header.index(col)
    return int(col)


def _cell(row: Sequence[Any] | Mapping[Any, Any], col: Any, *, header: Sequence[str] | None = None) -> Any:
    return row[col] if isinstance(row, Mapping) else row[_idx(header, col)]


def _null(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in _N)


def _date_candidates(v: Any) -> frozenset[date]:
    if isinstance(v, datetime):
        return frozenset({v.date()})
    if isinstance(v, date):
        return frozenset({v})
    s = str(v).strip()
    if not s or s.lower() in _N:
        return frozenset()
    found: set[date] = set()
    for f in _DF:
        try:
            found.add(datetime.strptime(s, f).date())
        except ValueError:
            pass
    return frozenset(found)


def _date(v: Any) -> date | None:
    candidates = _date_candidates(v)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None


def _dates_equal(a: Any, b: Any) -> bool:
    ca, cb = _date_candidates(a), _date_candidates(b)
    return bool(ca and cb and ca & cb)


def _lit(v: Any) -> Any:
    if isinstance(v, _C):
        return v
    s = str(v).strip()
    if not s or s[0] not in "[{(":
        return v
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return v


def _sig(v: Any, *, order: bool, complex_mode: bool) -> Any:
    parsed = _lit(v) if complex_mode else v
    if complex_mode and isinstance(parsed, dict):
        ks = parsed.keys() if order else sorted(parsed)
        return ("d", tuple((k, _sig(parsed[k], order=order, complex_mode=True)) for k in ks))
    if complex_mode and isinstance(parsed, (list, tuple)):
        xs = tuple(_sig(x, order=order, complex_mode=True) for x in parsed)
        return ("l", xs if order else tuple(sorted(xs, key=repr)))
    candidates = _date_candidates(parsed)
    if candidates:
        return ("D", min(candidates))
    raw = parsed if complex_mode else v
    return ("v", None if _null(raw) else str(raw).strip())


def eq(a: Any, b: Any, *, order: bool = False, complex_mode: bool = False) -> bool:
    if not complex_mode and _dates_equal(a, b):
        return True
    return _sig(a, order=order, complex_mode=complex_mode) == _sig(b, order=order, complex_mode=complex_mode)


def canonical_key(
    v: Any,
    *,
    mode: str = "auto",
    complex_mode: bool = False,
    order: bool = False,
) -> str:
    """Stable normalized string for row fingerprinting."""
    if mode in ("digits", "phone"):
        if _null(v):
            return "__NULL__"
        digits = _DIGITS.sub("", str(v))
        return digits if digits else "__NULL__"
    if mode == "text":
        if _null(v):
            return "__NULL__"
        return str(v).strip()
    if mode == "date":
        if _null(v):
            return "__NULL__"
        candidates = _date_candidates(v)
        if len(candidates) == 1:
            return next(iter(candidates)).isoformat()
        if candidates:
            return min(candidates).isoformat()
        return str(v).strip()
    if mode == "structured":
        complex_mode = True
    sig = _sig(v, order=order, complex_mode=complex_mode)
    if sig[0] == "v" and sig[1] is None:
        return "__NULL__"
    return repr(sig)


def col_pairs(
    sh: Sequence[str] | None,
    th: Sequence[str] | None,
    n: int,
) -> list[tuple[Any, Any]]:
    if sh and th:
        return list(zip(sh, th)) if len(sh) == len(th) else [(sh[i], th[i]) for i in range(min(len(sh), len(th)))]
    if sh:
        return [(c, i) for i, c in enumerate(sh)]
    if th:
        return [(i, c) for i, c in enumerate(th)]
    return [(i, i) for i in range(n)]


def scan_complex(
    rows: Iterable[Any],
    cols: Sequence[Any],
    n: int = 100,
    *,
    header: Sequence[str] | None = None,
) -> set[Any]:
    out: set[Any] = set()
    for i, row in enumerate(rows):
        if i >= n:
            break
        for c in cols:
            if isinstance(_lit(_cell(row, c, header=header)), _C):
                out.add(c)
    return out


def validate(
    src: Sequence[Any],
    tgt: Sequence[Any],
    *,
    source_header: Sequence[str] | None = None,
    target_header: Sequence[str] | None = None,
    key: Any | None = None,
    complex_order_sensitive: bool = False,
    scan_rows: int = 100,
) -> dict[str, Any]:
    n = max(len(src[0]) if src else 0, len(tgt[0]) if tgt else 0)
    pairs = col_pairs(source_header, target_header, n)
    tgt_by_src = dict(pairs)
    cmp_src = [sc for sc, _ in pairs if sc != key]
    cmp_tgt = [tgt_by_src[c] for c in cmp_src]
    complex_src = scan_complex(src, cmp_src, scan_rows, header=source_header)
    complex_tgt = scan_complex(tgt, cmp_tgt, scan_rows, header=target_header)
    complex_cols = complex_src | complex_tgt

    if key is None:
        sk = {i: i for i in range(len(src))}
        tk = {i: i for i in range(len(tgt))}
    else:
        tk_col = tgt_by_src.get(key, key)
        sk = {_cell(r, key, header=source_header): i for i, r in enumerate(src)}
        tk = {_cell(r, tk_col, header=target_header): i for i, r in enumerate(tgt)}

    mismatches: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = []

    for k, si in sk.items():
        if k not in tk:
            missing.append({"key": k, "source_row": src[si]})
            continue
        ti = tk[k]
        for sc, tc in pairs:
            if sc == key:
                continue
            a, b = _cell(src[si], sc, header=source_header), _cell(tgt[ti], tc, header=target_header)
            cm = sc in complex_cols
            if not eq(a, b, order=complex_order_sensitive if cm else False, complex_mode=cm):
                mismatches.append({"key": k, "column": sc, "source": a, "target": b})

    for k, ti in tk.items():
        if k not in sk:
            extra.append({"key": k, "target_row": tgt[ti]})

    return {
        "mismatches": mismatches,
        "missing_data": missing,
        "extra_data": extra,
        "complex_columns": sorted(complex_cols, key=str),
        "needs_order_preference": bool(complex_cols),
    }
