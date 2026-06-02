from pathlib import Path

import pytest

from pegasus.services.exceptions import ValidationBadRequestError
from pegasus.services.validation_service import ValidationService
from pegasus.validation.reconciliation.config import ReconciliationRuntimeConfig


def _csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_preflight_rejects_low_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    _csv(src, "id,x\n1,a\n")
    _csv(tgt, "id,x\n1,a\n")
    rcfg = ReconciliationRuntimeConfig(disk_headroom_multiplier=2.0)
    monkeypatch.setattr("pegasus.services.validation_service._available_disk_bytes", lambda _p=None: 1)
    monkeypatch.setattr("pegasus.services.validation_service._available_ram_bytes", lambda: 10 * 1024**3)
    with pytest.raises(ValidationBadRequestError, match="Insufficient disk"):
        ValidationService._preflight_resource_feasibility(source_path=src, target_path=tgt, rcfg=rcfg)


def test_preflight_rejects_low_ram(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    _csv(src, "id,x\n1,a\n")
    _csv(tgt, "id,x\n1,a\n")
    rcfg = ReconciliationRuntimeConfig(memory_budget_bytes=2 * 1024**3)
    monkeypatch.setattr("pegasus.services.validation_service._available_disk_bytes", lambda _p=None: 10 * 1024**3)
    monkeypatch.setattr("pegasus.services.validation_service._available_ram_bytes", lambda: 100 * 1024**2)
    with pytest.raises(ValidationBadRequestError, match="Insufficient RAM"):
        ValidationService._preflight_resource_feasibility(source_path=src, target_path=tgt, rcfg=rcfg)


def test_preflight_allows_sufficient_resources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    _csv(src, "id,x\n1,a\n")
    _csv(tgt, "id,x\n1,a\n")
    rcfg = ReconciliationRuntimeConfig(memory_budget_bytes=512 * 1024**2, disk_headroom_multiplier=1.0)
    monkeypatch.setattr("pegasus.services.validation_service._available_disk_bytes", lambda _p=None: 10 * 1024**3)
    monkeypatch.setattr("pegasus.services.validation_service._available_ram_bytes", lambda: 2 * 1024**3)
    ValidationService._preflight_resource_feasibility(source_path=src, target_path=tgt, rcfg=rcfg)
