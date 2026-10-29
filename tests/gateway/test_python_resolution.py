"""The patch sets find the Kiro Crew interpreter without assuming a pipx install.

``gateway-patches/sets/_kc_env.sh`` picks the interpreter (``KC_PYTHON``, then the
shebang of ``kirocrew`` on PATH, then the pipx venv) and the package directory
(``KC_SITE_OVERRIDE`` or that interpreter's ``kiro_crew``). Every test here runs
with an empty ``HOME``, so no pipx venv exists, and a PATH that holds only the
system tools plus what the test puts there.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import kiro_crew

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "gateway-patches" / "sets" / "_kc_env.sh"
SYSTEM_PATH = "/usr/bin:/bin"


def _env(tmp_path, **extra):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": SYSTEM_PATH, "LANG": "C.UTF-8"}
    env.update(extra)
    return env


def _resolve(env):
    script = f'source "{HELPER}"; kc_env "Set T" && echo "RESULT $KC_PY|$SITE"'
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)


def _result(r):
    line = next(x for x in r.stdout.splitlines() if x.startswith("RESULT "))
    py, site = line[len("RESULT ") :].split("|")
    return py, site


def _fake_kirocrew(tmp_path, interpreter):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    exe = bindir / "kirocrew"
    exe.write_text(f"#!{interpreter}\nimport sys\nsys.exit(0)\n")
    exe.chmod(0o755)
    return bindir


def _installed_site():
    return os.path.dirname(kiro_crew.__file__)


def test_kc_python_is_used(tmp_path):
    r = _resolve(_env(tmp_path, KC_PYTHON=sys.executable))
    assert r.returncode == 0, r.stdout + r.stderr
    py, site = _result(r)
    assert py == sys.executable
    assert Path(site) == Path(_installed_site())


def test_kirocrew_shebang_on_path_is_used(tmp_path):
    bindir = _fake_kirocrew(tmp_path, sys.executable)
    r = _resolve(_env(tmp_path, PATH=f"{bindir}:{SYSTEM_PATH}"))
    assert r.returncode == 0, r.stdout + r.stderr
    py, site = _result(r)
    assert py == sys.executable
    assert Path(site) == Path(_installed_site())


def test_kirocrew_symlink_like_cloud_install(tmp_path):
    bindir = _fake_kirocrew(tmp_path, sys.executable)
    linkdir = tmp_path / "local-bin"
    linkdir.mkdir()
    (linkdir / "kirocrew").symlink_to(bindir / "kirocrew")
    r = _resolve(_env(tmp_path, PATH=f"{linkdir}:{SYSTEM_PATH}"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert _result(r)[0] == sys.executable


def test_nothing_found_fails_loudly(tmp_path):
    r = _resolve(_env(tmp_path))
    assert r.returncode == 1
    out = r.stdout + r.stderr
    assert any(line.startswith("!!") and "KC_PYTHON" in line for line in out.splitlines()), out
    assert "RESULT" not in out


def test_bad_kc_python_fails_without_falling_back(tmp_path):
    bindir = _fake_kirocrew(tmp_path, sys.executable)
    r = _resolve(_env(tmp_path, PATH=f"{bindir}:{SYSTEM_PATH}", KC_PYTHON=str(tmp_path / "nope")))
    assert r.returncode == 1
    assert "KC_PYTHON" in r.stdout + r.stderr


def test_site_override_is_what_gets_imported(tmp_path):
    copy = tmp_path / "tree" / "kiro_crew"
    shutil.copytree(_installed_site(), copy, ignore=shutil.ignore_patterns("__pycache__"))
    script = (
        f'source "{HELPER}"; kc_env "Set T" || exit 1; '
        '"$KC_PY" -c "import kiro_crew; print(\'FILE\', kiro_crew.__file__)"'
    )
    env = _env(tmp_path, KC_PYTHON=sys.executable, KC_SITE_OVERRIDE=str(copy))
    r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(x for x in r.stdout.splitlines() if x.startswith("FILE "))
    assert Path(line[len("FILE ") :]) == copy / "__init__.py"


def test_site_override_without_package_fails(tmp_path):
    env = _env(tmp_path, KC_PYTHON=sys.executable, KC_SITE_OVERRIDE=str(tmp_path / "missing"))
    r = _resolve(env)
    assert r.returncode == 1
    assert any(line.startswith("!!") for line in (r.stdout + r.stderr).splitlines())


def _set_script(name):
    return next((REPO / "gateway-patches" / "sets").glob(f"repatch-set-{name}-*.sh"))


@pytest.mark.parametrize("name", ["n1", "n2", "n3", "n4"])
def test_n_set_runs_from_a_venv_outside_pipx(name, tmp_path):
    """The harness tree is already patched, so a run from a non-pipx venv is a verified no-op."""
    bindir = _fake_kirocrew(tmp_path, sys.executable)
    env = _env(tmp_path, PATH=f"{bindir}:{SYSTEM_PATH}")
    r = subprocess.run(["bash", str(_set_script(name))], env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert f"Set {name.upper()}: OK" in out
    assert "already applied" in out


@pytest.mark.parametrize("name", ["n1", "o3", "t"])
def test_set_without_interpreter_fails_instead_of_skipping(name, tmp_path):
    r = subprocess.run(["bash", str(_set_script(name))], env=_env(tmp_path), capture_output=True, text=True)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert "skipping" not in out
    assert any(line.startswith("!!") and "KC_PYTHON" in line for line in out.splitlines()), out
