"""Unit tests for scripts/_verify_common.sh, run through `bash -c` snippets."""

from __future__ import annotations

import os
import stat

from conftest import Sandbox


def test_vlog_vwarn_vdie_prefixes(sandbox: Sandbox) -> None:
    r = sandbox.bash("vlog hello world; vwarn careful; vdie boom 7")
    assert r.returncode == 7
    assert r.stdout == ">>> hello world\n"
    assert r.stderr == "-- warning: careful\n!! boom\n"


def test_vdie_default_code_is_1(sandbox: Sandbox) -> None:
    assert sandbox.bash("vdie nope").returncode == 1


def test_vusage_die_exits_2_and_points_at_help(sandbox: Sandbox) -> None:
    r = sandbox.bash("vusage_die 'bad flag'")
    assert r.returncode == 2
    assert r.stderr.splitlines()[0] == "!! bad flag"
    assert "see --help" in r.stderr


def test_vpy_ok_accepts_py312_rejects_missing_and_old(sandbox: Sandbox, py312: str) -> None:
    assert sandbox.bash(f'vpy_ok "{py312}"').returncode == 0
    assert sandbox.bash("vpy_ok /nonexistent/python").returncode != 0
    old = sandbox.stubs / "old-python"
    old.write_text("#!/bin/bash\nexit 1\n")
    old.chmod(0o755)
    assert sandbox.bash(f'vpy_ok "{old}"').returncode != 0


def test_vsafe_root_normalises(sandbox: Sandbox, tmp_path) -> None:
    r = sandbox.bash(f'vsafe_root "{tmp_path}/a/../b//c/"')
    assert r.returncode == 0
    assert r.stdout == f"{tmp_path}/b/c\n"


def test_vsafe_root_refuses_unsafe(sandbox: Sandbox) -> None:
    h = sandbox.home
    for bad in (
        "", "/", str(h), f"{h}/.kiro/crew", f"{h}/.kiro/crew/x",
        f"{h}/.local/share/pipx/venvs/kirocrew",
        f"{h}/.local/share/pipx/venvs/kirocrew/lib",
        f"{h}/x/../.kiro/crew/y",
    ):
        r = sandbox.bash(f'vsafe_root "{bad}"')
        assert r.returncode == 2, bad
        assert r.stderr.startswith("!! "), bad


def test_vsafe_root_allows_sibling_of_protected_paths(sandbox: Sandbox) -> None:
    for ok in (f"{sandbox.home}/.kiro/crew-verify", f"{sandbox.home}/work/verify"):
        r = sandbox.bash(f'vsafe_root "{ok}"')
        assert r.returncode == 0, ok
        assert r.stdout == ok + "\n"


def test_vrun_dry_run_prints_quoted_command_and_does_not_run(sandbox: Sandbox, tmp_path) -> None:
    marker = tmp_path / "ran"
    r = sandbox.bash(f'DRY_RUN=1 vrun touch "{marker}" "a b"')
    assert r.returncode == 0
    assert r.stdout.startswith("[dry-run] touch ")
    assert "a\\ b" in r.stdout
    assert not marker.exists()


def test_vrun_runs_for_real_otherwise(sandbox: Sandbox, tmp_path) -> None:
    marker = tmp_path / "ran"
    r = sandbox.bash(f'DRY_RUN=0 vrun touch "{marker}"')
    assert r.returncode == 0
    assert marker.exists()
    assert sandbox.bash("vrun false").returncode != 0


_ALL = {
    "VERIFY_FORMAT": "1", "ROOT": "/r", "NAME": "verify", "PORT": "8790",
    "KC_REF": "v0.10.0", "KC_SRC": "/r/kc-src", "VENV": "/r/venv",
    "KC_SITE": "/r/venv/lib/site-packages/kiro_crew", "KIROCREW_HOME": "/r/home",
    "UNIT": "kirocrew-verify-verify.service", "UNIT_FILE": "/u/kirocrew-verify-verify.service",
    "ADMIN_ENV_FILE": "",
}


def _assign(values: dict[str, str]) -> str:
    return "; ".join(f"{k}='{v}'" for k, v in values.items())


def test_env_roundtrip_mode_600_and_no_leftover_tmp(sandbox: Sandbox, tmp_path) -> None:
    d = tmp_path / "root"
    d.mkdir()
    f = d / "verify.env"
    snippet = (
        f"{_assign(_ALL)}; vwrite_env '{f}'; "
        + "; ".join(f'unset {k}' for k in _ALL)
        + f"; vread_env '{f}'; "
        + "; ".join(f'printf "%s=%s\\n" {k} "${{{k}}}"' for k in _ALL)
    )
    r = sandbox.bash(snippet)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [f"{k}={v}" for k, v in _ALL.items()]
    assert stat.S_IMODE(os.stat(f).st_mode) == 0o600
    assert f.read_text().splitlines() == [f"{k}={v}" for k, v in _ALL.items()]
    assert [p.name for p in d.iterdir()] == ["verify.env"]


def test_vwrite_env_refuses_newline(sandbox: Sandbox, tmp_path) -> None:
    f = tmp_path / "verify.env"
    r = sandbox.bash(f"{_assign(_ALL)}; NAME=$'a\\nb'; vwrite_env '{f}'")
    assert r.returncode != 0
    assert r.stderr.startswith("!! ")
    assert not f.exists()


def test_vread_env_does_not_source(sandbox: Sandbox, tmp_path) -> None:
    f = tmp_path / "verify.env"
    marker = tmp_path / "pwned"
    f.write_text(f"VERIFY_FORMAT=1\nROOT=$(touch {marker})\nNAME=a b;touch {marker}\n")
    r = sandbox.bash(f"vread_env '{f}'; printf '%s|%s' \"$ROOT\" \"$NAME\"")
    assert r.returncode == 0
    assert not marker.exists()
    assert r.stdout == f"$(touch {marker})|a b;touch {marker}"


def test_vread_env_rejects_unknown_key_and_malformed(sandbox: Sandbox, tmp_path) -> None:
    f = tmp_path / "verify.env"
    for body in ("EVIL=1\n", "ROOT\n", "ROOT /x\n", "root=/x\n", "VERIFY_FORMAT=2\n"):
        f.write_text(body)
        r = sandbox.bash(f"vread_env '{f}'")
        assert r.returncode != 0, body
        assert r.stderr.startswith("!! "), body


def test_vread_env_requires_verify_format(sandbox: Sandbox, tmp_path) -> None:
    f = tmp_path / "verify.env"
    f.write_text("ROOT=/r\nNAME=verify\n")
    r = sandbox.bash(f"vread_env '{f}'")
    assert r.returncode != 0
    assert r.stderr.startswith("!! ") and "VERIFY_FORMAT" in r.stderr
    f.write_text("")
    assert sandbox.bash(f"vread_env '{f}'").returncode != 0


def test_vread_env_missing_file(sandbox: Sandbox, tmp_path) -> None:
    r = sandbox.bash(f"vread_env '{tmp_path}/nope.env'")
    assert r.returncode != 0
    assert r.stderr.startswith("!! ")
