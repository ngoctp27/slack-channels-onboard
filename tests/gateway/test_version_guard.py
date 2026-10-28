"""The n* sets only know Kiro Crew 0.10.0 and must refuse any other version untouched."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import kiro_crew

REPO = Path(__file__).resolve().parents[2]
NSETS = ["n1"]  # Task 3-5 append "n2", "n3", "n4"


def _digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.mark.parametrize("name", NSETS)
def test_set_refuses_other_version(name, tmp_path):
    site = tmp_path / "kiro_crew"
    shutil.copytree(os.path.dirname(kiro_crew.__file__), site, ignore=shutil.ignore_patterns("__pycache__"))
    init = site / "__init__.py"
    init.write_text(init.read_text().replace('__version__ = "0.10.0"', '__version__ = "0.9.0"', 1))
    before = _digest(site)
    script = next((REPO / "gateway-patches" / "sets").glob(f"repatch-set-{name}-*.sh"))
    r = subprocess.run(
        ["bash", str(script)], env={**os.environ, "KC_SITE_OVERRIDE": str(site)}, capture_output=True, text=True
    )
    assert r.returncode == 1 and "CHECK ANCHORS" in r.stdout + r.stderr
    assert _digest(site) == before
