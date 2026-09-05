from __future__ import annotations

import sys
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session", autouse=True)
def qt_application() -> QApplication:
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_xdg_environment(tmp_path: Path, monkeypatch):
    """Prevent offline tests from reading or writing the desktop user's state."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
