"""Tests for scripts/verify-init.sh (argument handling, preflight, --dry-run)."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from conftest import Sandbox

SCRIPT = "verify-init.sh"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _ok(sandbox: Sandbox, py: str, root: Path, *extra: str, **env: str):
    return sandbox.run(SCRIPT, "--root", str(root), "--python", py,
                       "--port", str(_free_port()), *extra, **env)


def test_help_exits_0(sandbox: Sandbox) -> None:
    for flag in ("--help", "-h"):
        r = sandbox.run(SCRIPT, flag)
        assert r.returncode == 0
        assert "--root" in r.stdout
        assert "--dry-run" in r.stdout


def test_unknown_option_is_usage_error(sandbox: Sandbox) -> None:
    r = sandbox.run(SCRIPT, "--root", "/tmp/x", "--bogus")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_missing_root(sandbox: Sandbox, py312: str) -> None:
    r = sandbox.run(SCRIPT, "--python", py312, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_unsafe_roots(sandbox: Sandbox, py312: str) -> None:
    h = sandbox.home
    for bad in ("/", str(h), f"{h}/.kiro/crew", f"{h}/.kiro/crew/x",
                f"{h}/.local/share/pipx/venvs/kirocrew"):
        r = sandbox.run(SCRIPT, "--root", bad, "--python", py312, "--dry-run")
        assert r.returncode == 2, bad
        assert "!! " in r.stderr, bad


@pytest.mark.parametrize("port", ["abc", "80", "70000", "1023", "", "8790x"])
def test_bad_port(sandbox: Sandbox, py312: str, tmp_path, port: str) -> None:
    r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                    "--port", port, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


@pytest.mark.parametrize("name", ["Bad_Name", "-x", "", "a" * 32, "a.b"])
def test_bad_name(sandbox: Sandbox, py312: str, tmp_path, name: str) -> None:
    r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                    "--name", name, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_missing_or_non_regular_admin_env_file(sandbox: Sandbox, py312: str, tmp_path) -> None:
    for path in (tmp_path / "nope.env", tmp_path):
        r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                        "--admin-env-file", str(path), "--dry-run")
        assert r.returncode == 2, path
        assert "!! " in r.stderr


def test_python_too_old_is_fatal(sandbox: Sandbox, tmp_path) -> None:
    old = sandbox.stubs / "oldpy"
    old.write_text("#!/bin/bash\nexit 1\n")
    old.chmod(0o755)
    r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", str(old), "--dry-run")
    assert r.returncode != 0
    assert "!! " in r.stderr


def test_git_missing_is_fatal(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.hide("git")
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run")
    assert r.returncode != 0
    assert "!! " in r.stderr and "git" in r.stderr


def test_dry_run_lists_steps_in_order_and_creates_nothing(
    sandbox: Sandbox, py312: str, tmp_path
) -> None:
    root = tmp_path / "vroot"
    r = _ok(sandbox, py312, root, "--dry-run")
    assert r.returncode == 0, r.stderr
    plan = [l for l in r.stdout.splitlines() if l.startswith("[dry-run]")]
    labels = ["clone:", "venv+pip install:", "config set:", "slack setup:",
              "write unit:", "daemon-reload:", ". enable:", "write verify.env:"]
    idx = []
    for label in labels:
        hits = [i for i, l in enumerate(plan) if label in l]
        assert hits, f"missing step {label!r} in {plan}"
        idx.append(hits[0])
    assert idx == sorted(idx) and len(set(idx)) == len(idx)
    assert not any(". linger:" in l for l in plan)
    assert not root.exists()
    assert not sandbox.systemd_dir.exists()
    assert sandbox.calls("systemctl") == ["--user show-environment"]


def test_dry_run_skip_slack(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run", "--skip-slack")
    assert r.returncode == 0, r.stderr
    line = next(l for l in r.stdout.splitlines() if "slack setup:" in l)
    assert "skipped" in line


def test_dry_run_enable_linger_adds_step(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run", "--enable-linger")
    assert r.returncode == 0, r.stderr
    plan = [l for l in r.stdout.splitlines() if l.startswith("[dry-run]")]
    i_enable = next(i for i, l in enumerate(plan) if ". enable:" in l)
    i_linger = next(i for i, l in enumerate(plan) if ". linger:" in l)
    i_env = next(i for i, l in enumerate(plan) if "write verify.env:" in l)
    assert i_enable < i_linger < i_env


def test_dry_run_admin_env_file_stored_absolute_never_read(
    sandbox: Sandbox, py312: str, tmp_path
) -> None:
    f = tmp_path / "admins.env"
    f.write_text("KIROCREW_ADMIN_USER_IDS=SECRET_MARKER\n")
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run", "--admin-env-file", str(f))
    assert r.returncode == 0, r.stderr
    assert str(f) in r.stdout
    assert "SECRET_MARKER" not in r.stdout + r.stderr


def test_dry_run_systemctl_unusable_is_warning(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("systemctl", exit_code=1)
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "-- warning:" in r.stderr


def test_real_run_systemctl_unusable_is_fatal(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("systemctl", exit_code=1)
    r = _ok(sandbox, py312, tmp_path / "r")
    assert r.returncode == 1
    assert "!! " in r.stderr and "systemctl" in r.stderr


def test_bwrap_missing_warns_with_hint(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "-- warning:" in r.stderr and "sudo apt install bubblewrap" in r.stderr


def test_bwrap_present_no_warning(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("bwrap")
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "bubblewrap" not in r.stderr


def test_busy_port_is_fatal(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("systemctl", exit_code=0, body='[ "$2" = is-active ] && exit 3')
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                        "--port", str(port), "--dry-run")
    assert r.returncode == 1
    assert "!! " in r.stderr and str(port) in r.stderr


def test_busy_port_tolerated_when_unit_active(sandbox: Sandbox, py312: str, tmp_path) -> None:
    # Re-run of init: our own gateway holds the port and the unit is active.
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                        "--port", str(port), "--dry-run")
    assert r.returncode == 0, r.stderr
    assert sandbox.calls("systemctl")[-1].startswith("--user is-active")


@pytest.mark.parametrize("bad", ["a b", "a%b", 'a"b', "a\\b", "a\tb"])
def test_unit_unsafe_root_is_usage_error(sandbox: Sandbox, py312: str, tmp_path, bad: str) -> None:
    root = tmp_path / bad
    for extra in ((), ("--dry-run",), ("--skip-unit",)):
        r = _ok(sandbox, py312, root, *extra)
        assert r.returncode == 2, (bad, extra)
        assert "!! " in r.stderr
    assert not root.exists()


@pytest.mark.parametrize("bad", ["a b", "a%b", 'a"b', "a\\b"])
def test_unit_unsafe_admin_env_file_is_usage_error(
    sandbox: Sandbox, py312: str, tmp_path, bad: str
) -> None:
    f = tmp_path / bad
    f.write_text("KIROCREW_ADMIN_USER_IDS=X\n")
    root = tmp_path / "r"
    r = _ok(sandbox, py312, root, "--admin-env-file", str(f))
    assert r.returncode == 2
    assert "!! " in r.stderr
    assert not root.exists()
    assert sandbox.calls("systemctl") == []


def test_dry_run_slack_step_names_the_command(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run")
    line = next(l for l in r.stdout.splitlines() if "slack setup:" in l)
    assert "setup --slack" in line


def test_dry_run_skip_unit_marks_unit_steps_skipped(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("systemctl", exit_code=1)  # must not matter with --skip-unit
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run", "--skip-unit", "--enable-linger")
    assert r.returncode == 0, r.stderr
    assert "systemctl" not in r.stderr
    plan = [l for l in r.stdout.splitlines() if l.startswith("[dry-run]")]
    for label in ("write unit:", "daemon-reload:", ". enable:", ". linger:"):
        line = next(l for l in plan if label in l)
        assert "skipped" in line and "--skip-unit" in line, line
    assert sandbox.calls("systemctl") == []


def test_skip_unit_is_documented(sandbox: Sandbox) -> None:
    assert "--skip-unit" in sandbox.run(SCRIPT, "--help").stdout


def test_real_run_skip_unit_does_not_need_systemctl(sandbox: Sandbox, py312: str, tmp_path) -> None:
    sandbox.stub("systemctl", exit_code=1)
    sandbox.hide("git")  # stop right after preflight with a git error
    r = _ok(sandbox, py312, tmp_path / "r", "--skip-unit")
    assert r.returncode == 1
    assert "git" in r.stderr and "systemctl" not in r.stderr


def test_leading_dash_ref_is_usage_error(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = sandbox.run(SCRIPT, "--root", str(tmp_path / "r"), "--python", py312,
                    "--kc-ref", "--upload-pack=x", "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_leading_dash_repo_url_is_usage_error(sandbox: Sandbox, py312: str, tmp_path) -> None:
    r = _ok(sandbox, py312, tmp_path / "r", "--dry-run", KC_REPO_URL="--upload-pack=x")
    assert r.returncode == 2
    assert "!! " in r.stderr and "KC_REPO_URL" in r.stderr
