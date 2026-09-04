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
