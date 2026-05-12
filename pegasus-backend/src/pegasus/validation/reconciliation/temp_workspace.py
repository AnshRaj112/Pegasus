"""Temporary directory lifecycle for spill files and sorted runs."""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

_WORKSPACE_PREFIX: Final[str] = "pegasus_recon_"


@contextmanager
def temp_reconciliation_workspace(base_dir: Path | None = None) -> Iterator[Path]:
    """Create an isolated directory for spill/sort artifacts and remove it afterwards.

    Parameters
    ----------
    base_dir
        Optional parent directory (must exist). When ``None``, uses :func:`tempfile.gettempdir`.

    Yields
    ------
    pathlib.Path
        Empty workspace directory dedicated to one reconciliation run.
    """
    parent = base_dir if base_dir is not None else Path(tempfile.gettempdir())
    parent.mkdir(parents=True, exist_ok=True)
    run_tag = uuid.uuid4().hex[:12]
    root = Path(tempfile.mkdtemp(prefix=f"{_WORKSPACE_PREFIX}{run_tag}_", dir=str(parent)))
    logger.debug("Created reconciliation workspace %s", root)
    try:
        yield root
    finally:
        try:
            shutil.rmtree(root, ignore_errors=False)
        except OSError as exc:
            logger.warning("Failed to remove reconciliation workspace %s: %s", root, exc)
