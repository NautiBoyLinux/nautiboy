from __future__ import annotations

import re
import tomllib
from pathlib import Path
from xml.etree import ElementTree

from nautiboy import __version__


ROOT = Path(__file__).resolve().parents[1]


def test_public_beta_version_mapping_is_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"] == "0.4.0b1"

    metadata = ElementTree.parse(
        ROOT / "packaging/io.github.nautiboylinux.nautiboy.metainfo.xml"
    )
    releases = metadata.getroot().find("releases")
    assert releases is not None
    assert releases[0].attrib["version"] == "0.4.0-beta.1"

    spec = (ROOT / "packaging/fedora/nautiboy.spec").read_text(encoding="utf-8")
    assert re.search(r"^Version:\s+0\.4\.0~beta\.1$", spec, re.MULTILINE)
    assert re.search(r"^Release:\s+1%\{\?dist\}$", spec, re.MULTILINE)
    assert "v0.4.0-beta.1" in spec


def test_tester_documentation_exposes_version_support_and_compatibility() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    tester_guide = (ROOT / "docs/tester-guide.md").read_text(encoding="utf-8")
    for text in (readme, tester_guide):
        assert "v0.4.0-beta.1" in text
        assert "hardware@nautiboy.dev" in text
        assert "support@nautiboy.dev" in text
        assert "https://nautiboy.dev" in text
    assert "Identification does not imply control" in readme
    assert "sudo dnf install ./nautiboy-0.4.0~beta.1-1.fc44.noarch.rpm" in tester_guide
    assert "sudo dnf remove nautiboy" in tester_guide
