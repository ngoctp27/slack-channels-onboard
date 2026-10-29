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
    # Like kiro_crew.cli_setup in 0.10.0: the Slack-only step of the setup wizard.
    (repo / "src" / "kiro_crew" / "cli_setup.py").write_text(textwrap.dedent("""\
        import os
        import sys

        if not os.environ.get("FAKE_NO_SLACK_STEP"):
            def _setup_slack_tokens():
                with open(os.environ["FAKE_KC_LOG"], "a") as f:
                    f.write("slack tokens | " + os.environ.get("KIROCREW_HOME", "") + "\\n")
                if os.environ.get("FAKE_SLACK_FAIL"):
                    sys.exit(5)
        """))
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
                   KC_REPO_URL=f"file://{repo}", FAKE_KC_LOG=str(tmp / "kc-first.log"),
                   **_passthrough())
    if first.returncode != 0 and any(m in first.stdout + first.stderr for m in _NO_NET):
        pytest.skip("pip needs the network to fetch setuptools; none available")
    return Built(sb, py, repo, root, port, first)


def _env_dict(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines())


def _rerun(b: Built, *extra: str, **env: str) -> subprocess.CompletedProcess:
    args = ["--root", str(b.root), "--python", b.py, "--port", str(b.port),
            "--skip-slack", "--skip-unit", *extra]
    env.setdefault("FAKE_KC_LOG", str(b.sb.tmp / "kc-rerun.log"))
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
                     KC_REPO_URL=f"file://{built.repo}", FAKE_KC_LOG=str(built.sb.tmp / "kc-x.log"))
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


# ---- home config, Slack setup, systemd unit (Task 3) --------------------------
# These reuse the module's one real venv: each test gets its own ROOT whose
# venv/bin/{python,kirocrew} are thin wrappers around the built venv.

class Ctx(NamedTuple):
    b: Built
    root: Path
    sd: Path
    kc_log: Path
    port: int

    @property
    def home(self) -> Path:
        return self.root / "home"

    @property
    def unit_file(self) -> Path:
        return self.sd / "kirocrew-verify-verify.service"

    def kc_calls(self) -> list[str]:
        return self.kc_log.read_text().splitlines() if self.kc_log.exists() else []

    def run(self, *extra: str, **env: str) -> subprocess.CompletedProcess:
        if not (self.b.sb.stubs / "loginctl").exists():
            self.b.sb.stub("loginctl")
        self.b.sb.log.unlink(missing_ok=True)
        args = ["--root", str(self.root), "--python", self.b.py, "--port", str(self.port),
                *extra]
        return self.b.sb.run(SCRIPT, *args, KC_REPO_URL=f"file://{self.b.repo}",
                             SYSTEMD_USER_DIR=str(self.sd), FAKE_KC_LOG=str(self.kc_log), **env)


@pytest.fixture
def ctx(built: Built, tmp_path) -> Ctx:
    root = tmp_path / "froot"
    root.mkdir()
    _pre_clone(built, root)
    bindir = root / "venv" / "bin"
    bindir.mkdir(parents=True)
    for n in ("python", "kirocrew"):
        w = bindir / n
        w.write_text(f'#!/bin/bash\nexec "{built.root}/venv/bin/{n}" "$@"\n')
        w.chmod(0o755)
    return Ctx(built, root, tmp_path / "sd", tmp_path / "kc.log", _free_port())


def _unit_text(root: Path, port: int, admin: str = "") -> str:
    lines = [
        "[Unit]",
        "Description=Kiro Crew verify gateway (verify)",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=simple",
        f"Environment=KIROCREW_HOME={root}/home",
    ]
    if admin:
        lines.append(f"EnvironmentFile=-{admin}")
    lines += [
        f"ExecStart={root}/venv/bin/kirocrew gateway --no-open --no-tunnel --port {port}",
        "Restart=on-failure",
        "RestartSec=5",
        "",
        "[Install]",
        "WantedBy=default.target",
        "",
    ]
    return "\n".join(lines)


def _port_of(c: Ctx) -> int:
    return int(_env_dict(c.root / "verify.env")["PORT"])


def _strip_header(text: str) -> str:
    first, _, rest = text.partition("\n")
    return rest if first.startswith("# Written by scripts/verify-init.sh") else text


def test_config_set_calls_use_the_verify_home(ctx: Ctx) -> None:
    r = ctx.run("--skip-slack", "--skip-unit")
    assert r.returncode == 0, r.stderr
    port = _port_of(ctx)
    home = f"{ctx.root}/home"
    assert ctx.kc_calls() == [
        f"config set agent.apps_allow_third_party true | {home}",
        f"config set dashboard.url http://127.0.0.1:{port} | {home}",
    ]
    assert stat.S_IMODE(os.stat(ctx.home).st_mode) == 0o700


def test_skip_unit_still_configures_home_and_slack_but_writes_no_unit(ctx: Ctx) -> None:
    r = ctx.run("--skip-unit", "--enable-linger")
    assert r.returncode == 0, r.stderr
    assert any(c.startswith("config set") for c in ctx.kc_calls())
    assert "slack tokens" in " ".join(ctx.kc_calls())
    assert not ctx.sd.exists()
    assert ctx.b.sb.calls("systemctl") == []
    assert ctx.b.sb.calls("loginctl") == []


def test_unit_content_without_admin_env_file(ctx: Ctx) -> None:
    r = ctx.run("--skip-slack")
    assert r.returncode == 0, r.stderr
    text = ctx.unit_file.read_text()
    assert _strip_header(text) == _unit_text(ctx.root, _port_of(ctx))
    assert "EnvironmentFile" not in text
    assert "only when" not in text
    assert [l for l in text.splitlines() if l.startswith("#")] in ([], [text.splitlines()[0]])
    assert str(ctx.b.sb.home) not in text
    assert stat.S_IMODE(os.stat(ctx.unit_file).st_mode) == 0o644
    assert list(ctx.sd.iterdir()) == [ctx.unit_file]  # no temp file left behind


def test_unit_content_with_admin_env_file(ctx: Ctx, tmp_path) -> None:
    f = tmp_path / "admins.env"
    f.write_text("KIROCREW_ADMIN_USER_IDS=SECRET_MARKER\n")
    r = ctx.run("--skip-slack", "--admin-env-file", str(f))
    assert r.returncode == 0, r.stderr
    assert _strip_header(ctx.unit_file.read_text()) == _unit_text(ctx.root, _port_of(ctx), str(f))
    assert "SECRET_MARKER" not in r.stdout + r.stderr + ctx.unit_file.read_text()


def test_systemctl_gets_daemon_reload_then_enable_never_start(ctx: Ctx) -> None:
    r = ctx.run("--skip-slack")
    assert r.returncode == 0, r.stderr
    assert ctx.b.sb.calls("systemctl") == [
        "--user show-environment",
        "--user daemon-reload",
        "--user enable kirocrew-verify-verify.service",
    ]
    assert not any("start" in c or "restart" in c for c in ctx.b.sb.calls("systemctl"))


def test_unit_rerun_unchanged_skips_rewrite_and_reload_but_enables(ctx: Ctx) -> None:
    assert ctx.run("--skip-slack").returncode == 0
    before = ctx.unit_file.read_text()
    mtime = os.stat(ctx.unit_file).st_mtime_ns
    r = ctx.run("--skip-slack")
    assert r.returncode == 0, r.stderr
    assert ">>> unit: skipped (unchanged)" in r.stdout
    assert ctx.unit_file.read_text() == before
    assert os.stat(ctx.unit_file).st_mtime_ns == mtime
    assert ctx.b.sb.calls("systemctl") == [
        "--user show-environment",
        "--user enable kirocrew-verify-verify.service",
    ]


def test_unit_rerun_with_changed_content_rewrites_and_reloads(ctx: Ctx, tmp_path) -> None:
    assert ctx.run("--skip-slack").returncode == 0
    f = tmp_path / "admins.env"
    f.write_text("KIROCREW_ADMIN_USER_IDS=X\n")
    r = ctx.run("--skip-slack", "--admin-env-file", str(f))
    assert r.returncode == 0, r.stderr
    assert f"EnvironmentFile=-{f}" in ctx.unit_file.read_text()
    assert "unchanged" not in r.stdout
    assert "--user daemon-reload" in ctx.b.sb.calls("systemctl")


def test_linger_only_with_flag(ctx: Ctx) -> None:
    ctx.b.sb.stub("loginctl")
    assert ctx.run("--skip-slack").returncode == 0
    assert ctx.b.sb.calls("loginctl") == []
    r = ctx.run("--skip-slack", "--enable-linger", USER="someone")
    assert r.returncode == 0, r.stderr
    assert ctx.b.sb.calls("loginctl") == ["enable-linger someone"]
    assert not any("sudo" in c for c in ctx.b.sb.calls("loginctl"))


def test_linger_failure_is_a_warning_with_hint(ctx: Ctx) -> None:
    ctx.b.sb.stub("loginctl", exit_code=1)
    r = ctx.run("--skip-slack", "--enable-linger", USER="someone")
    assert r.returncode == 0, r.stderr
    assert "-- warning:" in r.stderr and "enable-linger" in r.stderr
    ctx.b.sb.stub("loginctl")


def test_systemctl_enable_failure_is_fatal(ctx: Ctx) -> None:
    ctx.b.sb.stub("systemctl", body='[ "$2" = enable ] && exit 1')
    r = ctx.run("--skip-slack")
    assert r.returncode == 1
    assert "!! " in r.stderr and not (ctx.root / "verify.env").exists()
    ctx.b.sb.stub("systemctl")


def test_final_message_names_next_step(ctx: Ctx) -> None:
    r = ctx.run("--skip-slack")
    assert r.returncode == 0, r.stderr
    assert f"scripts/verify-install.sh --root {ctx.root} --pr <N>" in r.stdout
    assert (ctx.root / "verify.env").exists()


# Slack: the .env is only probed, never printed.

def _write_dotenv(ctx: Ctx, text: str) -> None:
    ctx.home.mkdir(mode=0o700, exist_ok=True)
    (ctx.home / ".env").write_text(text)


def test_slack_setup_runs_when_tokens_missing(ctx: Ctx) -> None:
    r = ctx.run("--skip-unit")
    assert r.returncode == 0, r.stderr
    assert f"slack tokens | {ctx.root}/home" in ctx.kc_calls()
    assert "skipped (tokens already set)" not in r.stdout


def test_slack_setup_skipped_when_both_tokens_present(ctx: Ctx) -> None:
    _write_dotenv(ctx, "SLACK_BOT_TOKEN=xoxb-test-not-real\nSLACK_APP_TOKEN=xapp-test-not-real\n")
    r = ctx.run("--skip-unit")
    assert r.returncode == 0, r.stderr
    assert not any(c.startswith(("setup", "slack tokens")) for c in ctx.kc_calls())
    assert ">>> slack: skipped (tokens already set)" in r.stdout
    out = r.stdout + r.stderr
    assert "xoxb-test-not-real" not in out and "xapp-test-not-real" not in out


@pytest.mark.parametrize("text", [
    "SLACK_BOT_TOKEN=xoxb-test-not-real\n",
    "SLACK_APP_TOKEN=xapp-test-not-real\n",
    "SLACK_BOT_TOKEN=xoxb-test-not-real\nSLACK_APP_TOKEN=\n",
    "SLACK_BOT_TOKEN=\nSLACK_APP_TOKEN=xapp-test-not-real\n",
    "# SLACK_BOT_TOKEN=xoxb-test-not-real\nSLACK_APP_TOKEN=xapp-test-not-real\n",
])
def test_slack_setup_runs_when_one_token_missing_or_empty(ctx: Ctx, text: str) -> None:
    _write_dotenv(ctx, text)
    r = ctx.run("--skip-unit")
    assert r.returncode == 0, r.stderr
    assert f"slack tokens | {ctx.root}/home" in ctx.kc_calls()
    out = r.stdout + r.stderr
    assert "xoxb-test-not-real" not in out and "xapp-test-not-real" not in out


def test_skip_slack_never_calls_setup(ctx: Ctx) -> None:
    r = ctx.run("--skip-slack", "--skip-unit")
    assert r.returncode == 0, r.stderr
    assert not any(c.startswith(("setup", "slack tokens")) for c in ctx.kc_calls())


def test_slack_setup_failure_is_fatal(ctx: Ctx) -> None:
    r = ctx.run(FAKE_SLACK_FAIL="1")
    assert r.returncode != 0
    assert "!! " in r.stderr and "slack" in r.stderr.lower()
    assert not (ctx.root / "verify.env").exists()


def test_slack_step_never_runs_the_whole_setup_wizard(ctx: Ctx) -> None:
    # `kirocrew setup` also installs the agent spec, claims ~/.local/bin/kirocrew
    # and asks for the dashboard URL; only its Slack step is wanted here.
    r = ctx.run("--skip-unit")
    assert r.returncode == 0, r.stderr
    assert not any(c.startswith("setup") for c in ctx.kc_calls())
    assert f"slack tokens | {ctx.root}/home" in ctx.kc_calls()


def test_missing_slack_step_falls_back_to_the_dashboard(ctx: Ctx) -> None:
    r = ctx.run("--skip-unit", FAKE_NO_SLACK_STEP="1")
    assert r.returncode == 0, r.stderr
    assert "dashboard" in r.stderr.lower() and "_setup_slack_tokens" in r.stderr
    assert not any(c.startswith(("setup", "slack tokens")) for c in ctx.kc_calls())
    assert (ctx.root / "verify.env").exists()


def test_dry_run_with_venv_calls_nothing(ctx: Ctx) -> None:
    r = ctx.run("--dry-run")
    assert r.returncode == 0, r.stderr
    assert ctx.kc_calls() == []
    assert ctx.b.sb.calls("systemctl") == ["--user show-environment"]
    assert ctx.b.sb.calls("loginctl") == []
    assert not ctx.sd.exists() and not ctx.home.exists()


# ---- dashboard frontend: website/ built into kc-src/src/kiro_crew/static/dist ----
# node and npm are stubs; npm `run build` writes website/dist/index.html.

def _website(ctx: Ctx) -> Path:
    w = ctx.root / "kc-src" / "website"
    w.mkdir(exist_ok=True)
    (w / "package.json").write_text("{}\n")
    (w / "package-lock.json").write_text("{}\n")
    return w


def _node(ctx: Ctx, version: str = "24.1.0") -> None:
    ctx.b.sb.stub("node", body=f'[ "$1" = -p ] && echo {version}')


def _npm(ctx: Ctx, build_rc: int = 0) -> None:
    ctx.b.sb.stub("npm", body=(
        'if [ "$1 $2" = "run build" ]; then\n'
        f'  [ {build_rc} = 0 ] || {{ echo "vite: boom" >&2; exit {build_rc}; }}\n'
        '  mkdir -p dist && echo "<html>" > dist/index.html\n'
        "fi"))


def _dist(ctx: Ctx) -> Path:
    return ctx.root / "kc-src" / "src" / "kiro_crew" / "static" / "dist" / "index.html"


def _drop_frontend_stubs(ctx: Ctx) -> None:
    for n in ("node", "npm"):
        (ctx.b.sb.stubs / n).unlink(missing_ok=True)


def test_frontend_is_built_into_the_pristine_tree(ctx: Ctx) -> None:
    _website(ctx); _node(ctx); _npm(ctx)
    try:
        r = ctx.run("--skip-slack", "--skip-unit")
        assert r.returncode == 0, r.stderr
        assert _dist(ctx).read_text() == "<html>\n"
        assert ctx.b.sb.calls("npm")[:2] == [
            f"ci --no-audit --no-fund --loglevel=error --cache {ctx.root}/state/npm-cache",
            "run build"]
        assert list((ctx.root / "logs").glob("frontend-*.log"))
        # re-run: already built, npm is not called again
        ctx.b.sb.log.unlink(missing_ok=True)
        r = ctx.run("--skip-slack", "--skip-unit")
        assert r.returncode == 0, r.stderr
        assert ">>> frontend: skipped (already done)" in r.stdout
        assert ctx.b.sb.calls("npm") == []
    finally:
        _drop_frontend_stubs(ctx)


def test_frontend_without_node_warns_and_continues(ctx: Ctx) -> None:
    _website(ctx)
    _drop_frontend_stubs(ctx)
    r = ctx.run("--skip-slack", "--skip-unit")
    assert r.returncode == 0, r.stderr
    assert "-- warning:" in r.stderr and "legacy" in r.stderr and "22.12" in r.stderr
    assert not _dist(ctx).exists()
    assert (ctx.root / "verify.env").exists()


def test_frontend_with_old_node_warns_and_skips_npm(ctx: Ctx) -> None:
    _website(ctx); _node(ctx, "20.11.1"); _npm(ctx)
    try:
        r = ctx.run("--skip-slack", "--skip-unit")
        assert r.returncode == 0, r.stderr
        assert "20.11.1" in r.stderr and "22.12" in r.stderr
        assert ctx.b.sb.calls("npm") == []
    finally:
        _drop_frontend_stubs(ctx)


def test_frontend_build_failure_warns_with_the_log(ctx: Ctx) -> None:
    _website(ctx); _node(ctx); _npm(ctx, build_rc=1)
    try:
        r = ctx.run("--skip-slack", "--skip-unit")
        assert r.returncode == 0, r.stderr
        assert "-- warning:" in r.stderr and "frontend-" in r.stderr
        assert not _dist(ctx).exists()
    finally:
        _drop_frontend_stubs(ctx)


def test_skip_frontend_never_calls_npm(ctx: Ctx) -> None:
    _website(ctx); _node(ctx); _npm(ctx)
    try:
        r = ctx.run("--skip-slack", "--skip-unit", "--skip-frontend")
        assert r.returncode == 0, r.stderr
        assert ">>> frontend: skipped (--skip-frontend)" in r.stdout
        assert ctx.b.sb.calls("npm") == [] and ctx.b.sb.calls("node") == []
    finally:
        _drop_frontend_stubs(ctx)


@pytest.mark.parametrize("version,ok", [
    ("22.11.0", False), ("22.12.0", True), ("23.0.1", True), ("9.99.0", False), ("100.0.0", True),
])
def test_frontend_node_version_floor(ctx: Ctx, version: str, ok: bool) -> None:
    try:
        _website(ctx); _node(ctx, version); _npm(ctx)
        r = ctx.run("--skip-slack", "--skip-unit")
        assert r.returncode == 0, r.stderr
        assert _dist(ctx).exists() is ok
        assert bool(ctx.b.sb.calls("npm")) is ok
    finally:
        _drop_frontend_stubs(ctx)


def test_frontend_npm_cache_stays_under_the_root(ctx: Ctx) -> None:
    try:
        _website(ctx); _node(ctx); _npm(ctx)
        assert ctx.run("--skip-slack", "--skip-unit").returncode == 0
        ci = ctx.b.sb.calls("npm")[0]
        assert ci.startswith("ci ") and f"--cache {ctx.root}/state/npm-cache" in ci
    finally:
        _drop_frontend_stubs(ctx)
