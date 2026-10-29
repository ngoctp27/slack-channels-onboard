"""verify-init.sh steps 1-2 and verify.env, against a fake Kiro Crew repo.

One real venv + pip build per module (module-scoped fixture). pip needs the
network to fetch setuptools for build isolation; without it the module skips.
"""

from __future__ import annotations

import os
import socket
import stat
import subprocess
import textwrap
from pathlib import Path
from typing import NamedTuple

import pytest

from conftest import Sandbox, find_python312

SCRIPT = "verify-init.sh"
_NO_NET = ("Could not find a version that satisfies", "No matching distribution",
           "Temporary failure in name resolution", "Network is unreachable",
           "Connection refused", "Max retries exceeded", "ProxyError")
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_fake_kirocrew(repo: Path, tag: str = "v0.10.0") -> None:
    (repo / "src" / "kiro_crew").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(textwrap.dedent("""\
        [build-system]
        requires = ["setuptools>=61"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "kiro-crew-fake"
        version = "0.10.0"

        [project.scripts]
        kirocrew = "kiro_crew.cli:main"

        [tool.setuptools.packages.find]
        where = ["src"]
        """))
    (repo / "src" / "kiro_crew" / "__init__.py").write_text("")
    (repo / "src" / "kiro_crew" / "cli.py").write_text(textwrap.dedent("""\
        import os
        import sys


        def main():
            if sys.argv[1:] == ["--version"]:
                print("kirocrew 0.10.0")
                return 0
            with open(os.environ["FAKE_KC_LOG"], "a") as f:
                f.write(" ".join(sys.argv[1:]) + " | " + os.environ.get("KIROCREW_HOME", "") + "\\n")
            return 0
        """))
    env = {**os.environ, **_GIT_ENV}
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "fake"],
                ["tag", tag]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, env=env,
                       capture_output=True)


def _passthrough() -> dict[str, str]:
    keys = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "no_proxy",
            "NO_PROXY", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "PIP_INDEX_URL",
            "PIP_EXTRA_INDEX_URL")
    return {k: os.environ[k] for k in keys if k in os.environ}


class Built(NamedTuple):
    sb: Sandbox
    py: str
    repo: Path
    root: Path
    port: int
    first: subprocess.CompletedProcess


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Built:
    py = find_python312()
    if not py:
        pytest.skip("needs a Python >= 3.12 interpreter")
    tmp = tmp_path_factory.mktemp("vinit")
    sb = Sandbox(tmp)
    sb.stub("systemctl")
    repo = tmp / "fake-kc"
    make_fake_kirocrew(repo)
    root = tmp / "vroot"
    port = _free_port()
    first = sb.run(SCRIPT, "--root", str(root), "--python", py, "--port", str(port),
                   "--skip-slack", "--skip-unit",
                   KC_REPO_URL=f"file://{repo}", **_passthrough())
    if first.returncode != 0 and any(m in first.stdout + first.stderr for m in _NO_NET):
        pytest.skip("pip needs the network to fetch setuptools; none available")
    return Built(sb, py, repo, root, port, first)


def _env_dict(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def _rerun(b: Built, *extra: str, **env: str) -> subprocess.CompletedProcess:
    args = ["--root", str(b.root), "--python", b.py, "--port", str(b.port),
            "--skip-slack", "--skip-unit", *extra]
    return b.sb.run(SCRIPT, *args, KC_REPO_URL=f"file://{b.repo}", **env)


def test_first_run_builds_clone_and_venv(built: Built) -> None:
    assert built.first.returncode == 0, built.first.stderr
    root = built.root
    assert stat.S_IMODE(os.stat(root).st_mode) == 0o700
    for d in ("logs", "state", "checkouts", "kc-src/.git", "venv/bin/python"):
        assert (root / d).exists(), d
    r = subprocess.run([str(root / "venv/bin/kirocrew"), "--version"],
                       capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == "kirocrew 0.10.0"


def test_verify_env_keys_values_and_mode(built: Built) -> None:
    f = built.root / "verify.env"
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600
    e = _env_dict(f)
    root = str(built.root)
    sd = str(built.sb.systemd_dir)
    assert e["VERIFY_FORMAT"] == "1"
    assert e["ROOT"] == root
    assert e["NAME"] == "verify"
    assert e["PORT"] == str(built.port)
    assert e["KC_REF"] == "v0.10.0"
    assert e["KC_SRC"] == f"{root}/kc-src"
    assert e["VENV"] == f"{root}/venv"
    assert e["KC_SITE"].endswith("site-packages/kiro_crew")
    assert e["KC_SITE"].startswith(f"{root}/venv/")
    assert e["KIROCREW_HOME"] == f"{root}/home"
    assert e["UNIT"] == "kirocrew-verify-verify.service"
    assert e["UNIT_FILE"] == f"{sd}/kirocrew-verify-verify.service"
    assert e["ADMIN_ENV_FILE"] == ""
    assert not built.sb.systemd_dir.exists()
    assert built.sb.calls("systemctl") == []


def test_second_run_is_idempotent(built: Built) -> None:
    before = (built.root / "verify.env").read_text()
    r = _rerun(built)
    assert r.returncode == 0, r.stderr
    assert "clone: skipped (already done)" in r.stdout
    assert "venv: skipped (already done)" in r.stdout
    assert "pip install: skipped (already done)" in r.stdout
    assert (built.root / "verify.env").read_text() == before


def test_rerun_with_other_port_is_refused(built: Built) -> None:
    before = (built.root / "verify.env").read_text()
    r = built.sb.run(SCRIPT, "--root", str(built.root), "--python", built.py,
                     "--port", str(_free_port()), "--skip-slack", "--skip-unit",
                     KC_REPO_URL=f"file://{built.repo}")
    assert r.returncode == 2
    assert "!! " in r.stderr and "PORT" in r.stderr
    assert (built.root / "verify.env").read_text() == before


def test_rerun_with_other_name_or_ref_is_refused(built: Built) -> None:
    for extra, word in ((("--name", "other"), "NAME"), (("--kc-ref", "v9.9.9"), "KC_REF")):
        r = _rerun(built, *extra)
        assert r.returncode == 2, extra
        assert "!! " in r.stderr and word in r.stderr


def test_rerun_keeps_recorded_admin_env_file(built: Built, tmp_path) -> None:
    f = tmp_path / "admins.env"
    f.write_text("KIROCREW_ADMIN_USER_IDS=X\n")
    r = _rerun(built, "--admin-env-file", str(f))
    assert r.returncode == 0, r.stderr
    assert _env_dict(built.root / "verify.env")["ADMIN_ENV_FILE"] == str(f)
    r = _rerun(built)
    assert r.returncode == 0, r.stderr
    assert _env_dict(built.root / "verify.env")["ADMIN_ENV_FILE"] == str(f)


# ---- kc-src ref check without a verify.env (no venv build) -------------------

def _pre_clone(b: Built, root: Path, ref: str = "v0.10.0") -> None:
    subprocess.run(["git", "clone", "-q", "-c", "advice.detachedHead=false", "--branch", ref,
                    f"file://{b.repo}", str(root / "kc-src")], check=True, capture_output=True,
                   env={**os.environ, **_GIT_ENV})


def test_existing_clone_with_other_ref_is_refused(built: Built, tmp_path) -> None:
    root = tmp_path / "other-root"
    root.mkdir()
    _pre_clone(built, root)
    r = built.sb.run(SCRIPT, "--root", str(root), "--python", built.py,
                     "--port", str(_free_port()), "--skip-slack", "--skip-unit",
                     "--kc-ref", "main", KC_REPO_URL=f"file://{built.repo}")
    assert r.returncode != 0
    assert "!! " in r.stderr and "kc-src" in r.stderr and "--root" in r.stderr
    assert (root / "kc-src").is_dir()  # never deleted
    assert not (root / "venv").exists()


def test_existing_clone_with_matching_ref_is_accepted(built: Built, tmp_path) -> None:
    root = tmp_path / "match-root"
    root.mkdir()
    _pre_clone(built, root)
    # A python wrapper whose `-m venv` fails: proves the run got past the ref check.
    wrapper = built.sb.stubs / "pywrap"
    wrapper.write_text(f'#!/bin/bash\n[ "$1 $2" = "-m venv" ] && exit 7\nexec "{built.py}" "$@"\n')
    wrapper.chmod(0o755)
    r = built.sb.run(SCRIPT, "--root", str(root), "--python", str(wrapper),
                     "--port", str(_free_port()), "--skip-slack", "--skip-unit",
                     KC_REPO_URL=f"file://{built.repo}")
    assert "clone: skipped (already done)" in r.stdout
    assert r.returncode != 0  # the stubbed venv build fails
    assert not (root / "verify.env").exists()
