"""Helpers for driving scripts/verify-*.sh in a sandbox.

Every run gets a tmp HOME, a tmp SYSTEMD_USER_DIR and a minimal PATH made of
stub binaries (which log their argv) plus symlinks to the few real tools the
scripts need. Nothing here touches the real home, systemd or the network.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"

# Real tools the scripts may call. Anything else must come from a stub.
_REAL_TOOLS = (
    "bash", "env", "git", "realpath", "dirname", "basename", "mktemp", "mv",
    "mkdir", "cat", "chmod", "rm", "ls", "grep", "sed", "tr", "head", "sort",
    "readlink", "uname", "id", "date", "sleep", "cp", "ln", "touch", "wc", "stat",
)


def find_python312() -> str | None:
    if sys.version_info >= (3, 12):
        return sys.executable
    return shutil.which("python3.12")


@pytest.fixture
def py312() -> str:
    found = find_python312()
    if not found:
        pytest.skip("needs a Python >= 3.12 interpreter")
    return found


class Sandbox:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.home = tmp / "home"
        self.home.mkdir()
        self.systemd_dir = tmp / "systemd-user"
        self.stubs = tmp / "stubs"
        self.stubs.mkdir()
        self.tools = tmp / "tools"
        self.tools.mkdir()
        self.log = tmp / "calls.log"
        for name in _REAL_TOOLS:
            real = shutil.which(name)
            if real:
                (self.tools / name).symlink_to(real)

    def stub(self, name: str, *, exit_code: int = 0, body: str = "") -> Path:
        """A stub binary that appends its argv to calls.log, runs BODY, exits."""
        path = self.stubs / name
        path.write_text(
            "#!/bin/bash\n"
            f'printf \'%s %s\\n\' {name!r} "$*" >> "{self.log}"\n'
            f"{body}\n"
            f"exit {exit_code}\n"
        )
        path.chmod(0o755)
        return path

    def hide(self, name: str) -> None:
        """Remove a real tool from the minimal PATH."""
        link = self.tools / name
        if link.is_symlink():
            link.unlink()

    def calls(self, name: str) -> list[str]:
        if not self.log.exists():
            return []
        prefix = f"{name} "
        return [
            line[len(prefix):]
            for line in self.log.read_text().splitlines()
            if line.startswith(prefix)
        ]

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            "HOME": str(self.home),
            "SYSTEMD_USER_DIR": str(self.systemd_dir),
            "PATH": f"{self.stubs}:{self.tools}",
            "LC_ALL": "C",
        }
        env.update(extra)
        return env

    def run(self, script: str, *args: str, **extra_env: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(self.tools / "bash"), str(SCRIPTS / script), *args],
            env=self.env(**extra_env),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def bash(self, snippet: str, **extra_env: str) -> subprocess.CompletedProcess:
        """Run a bash snippet with the common library sourced."""
        return subprocess.run(
            [str(self.tools / "bash"), "-c",
             f'set -euo pipefail; source "{SCRIPTS}/_verify_common.sh"; {snippet}'],
            env=self.env(**extra_env),
            capture_output=True,
            text=True,
            timeout=60,
        )


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    sb = Sandbox(tmp_path)
    sb.stub("systemctl")  # `show-environment` succeeds by default
    return sb
