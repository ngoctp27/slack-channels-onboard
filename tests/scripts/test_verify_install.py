"""Tests for scripts/verify-install.sh: argument handling and source selection.

A bare "remote" in tmp_path carries a commit on refs/pull/1/head and a branch
feat/x; a local clone of it is the --repo. Git runs with an isolated config
(tmp HOME, no system config, placeholder identity). No network is used.

A real run goes through stop, reset, apply, the app reinstall, start, the health
poll and the journal scan. All of it runs against a fake venv (with a real
python wrapper and a fake kirocrew), a fake pristine Kiro Crew tree, a fake
gateway-patches/apply.sh and stub systemctl, curl and journalctl. Every stub
logs its argv, in order, to the one calls.log of the sandbox.
"""

from __future__ import annotations

import os
import shutil
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

from conftest import SCRIPTS, Sandbox

SCRIPT = "verify-install.sh"
# Fast health polling for the tests; the real defaults are 60 s, 5 s and 2 s.
_RUN_ENV = {
    "VERIFY_HEALTH_TIMEOUT": "2",
    "VERIFY_SETTLE_SECS": "0",
    "VERIFY_HEALTH_INTERVAL": "0.2",
}
_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "placeholder",
    "GIT_AUTHOR_EMAIL": "placeholder@example.invalid",
    "GIT_COMMITTER_NAME": "placeholder",
    "GIT_COMMITTER_EMAIL": "placeholder@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}


class Fx(NamedTuple):
    sb: Sandbox
    remote: Path   # bare repo, the "origin" of repo
    seed: Path     # working repo used to move refs in the remote
    repo: Path     # local clone, passed as --repo
    root: Path     # verify root with a hand-written verify.env
    sha: str       # first commit (refs/pull/1/head, feat/x)

    def env(self) -> dict[str, str]:
        return {**self.sb.env(), **_GIT_ENV}

    def git(self, repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", "-C", str(repo), *args], env=self.env(),
                           capture_output=True, text=True, check=False, timeout=60)
        if check and r.returncode != 0:
            raise AssertionError(f"git {args} failed: {r.stderr}")
        return r

    def install(self, *args: str, repo: bool = True, root: bool = True,
                extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        full: list[str] = []
        if root:
            full += ["--root", str(self.root)]
        if repo:
            full += ["--repo", str(self.repo)]
        env = {**_GIT_ENV, **_RUN_ENV, "FAKE_CALLS_LOG": str(self.sb.log),
               "FAKE_KC_HOME_LOG": str(self.kc_home_log), **(extra or {})}
        return self.sb.run(SCRIPT, *full, *args, **env)

    @property
    def kc_home_log(self) -> Path:
        return self.sb.tmp / "kirocrew-home.log"

    @property
    def journal(self) -> Path:
        return self.sb.tmp / "journal.txt"

    @property
    def state(self) -> Path:
        return self.root / "state" / "current.json"

    @property
    def app_dir(self) -> Path:
        return self.root / "home" / "apps" / "slack-channels-onboard"

    def calls_log(self) -> list[str]:
        """Every stub call in order, as \"name argv\"; curl polls are collapsed."""
        out: list[str] = []
        for ln in self.sb.log.read_text().splitlines() if self.sb.log.exists() else []:
            if ln.startswith("curl ") and out and out[-1].startswith("curl "):
                continue
            out.append(ln)
        return out

    @property
    def site(self) -> Path:
        return self.root / "venv" / "lib" / "site-packages" / "kiro_crew"

    @property
    def src_pkg(self) -> Path:
        return self.root / "kc-src" / "src" / "kiro_crew"

    @property
    def apply_log(self) -> Path:
        return self.sb.tmp / "apply-calls.log"

    def applies(self) -> list[str]:
        """argv lines the fake apply.sh logged, one per run."""
        if not self.apply_log.exists():
            return []
        return [ln for ln in self.apply_log.read_text().splitlines() if ln.startswith("argv:")]

    def logs(self) -> list[Path]:
        d = self.root / "logs"
        return sorted(d.glob("apply-*.log")) if d.is_dir() else []

    def write_env(self, **overrides: str) -> None:
        """Rewrite verify.env with OVERRIDES applied to the defaults."""
        _write_env(self.root, **overrides)

    def commit(self, files: dict[str, str], msg: str = "c") -> str:
        for rel, text in files.items():
            p = self.seed / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        self.git(self.seed, "add", "-A")
        self.git(self.seed, "commit", "-q", "-m", msg)
        return self.git(self.seed, "rev-parse", "HEAD").stdout.strip()

    def heads(self) -> str:
        return self.git(self.repo, "for-each-ref", "refs/heads").stdout

    def worktrees(self) -> list[str]:
        out = self.git(self.repo, "worktree", "list", "--porcelain").stdout
        return [ln[len("worktree "):] for ln in out.splitlines() if ln.startswith("worktree ")]

    def head_of(self, d: Path) -> str:
        return self.git(d, "rev-parse", "HEAD").stdout.strip()


def _write_env(root: Path, **overrides: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    kv = {
        "VERIFY_FORMAT": "1", "ROOT": str(root), "NAME": "verify", "PORT": "8790",
        "KC_REF": "v0.10.0", "KC_SRC": f"{root}/kc-src", "VENV": f"{root}/venv",
        "KC_SITE": f"{root}/venv/lib/site-packages/kiro_crew",
        "KIROCREW_HOME": f"{root}/home", "UNIT": "kirocrew-verify-verify.service",
        "UNIT_FILE": f"{root}/unit.service", "ADMIN_ENV_FILE": "",
    }
    kv.update(overrides)
    (root / "verify.env").write_text("".join(f"{k}={v}\n" for k, v in kv.items()))


# A fake apply.sh. FAKE_APPLY_LOG gets one "argv:" line per run plus the env it
# saw; FAKE_APPLY_MODE picks the behaviour; "second-*" modes only misbehave on
# the second call.
_FAKE_APPLY = r"""#!/bin/bash
log="${FAKE_APPLY_LOG:-/dev/null}"
n=$(cat "$log.n" 2>/dev/null || echo 0); n=$((n + 1))
if [ -n "${FAKE_APPLY_LOG:-}" ]; then echo "$n" > "$log.n"; fi
echo "apply.sh $*" >> "${FAKE_CALLS_LOG:-/dev/null}"
{
  echo "argv: $*"
  echo "KC_SITE_OVERRIDE=${KC_SITE_OVERRIDE-unset}"
  echo "KC_PYTHON=${KC_PYTHON-unset}"
  echo "stale_present=$(ls "$KC_SITE_OVERRIDE" 2>/dev/null | grep -c bak-setb || true)"
} >> "$log"
mode="${FAKE_APPLY_MODE:-ok}"
case "$mode" in second-*) if [ "$n" -ge 2 ]; then mode="${mode#second-}"; else mode=ok; fi ;; esac
case "$mode" in
  ok) echo "applying"; echo "All sets applied" ;;
  anchors) echo "CHECK ANCHORS in foo.py"; echo "All sets applied" ;;
  exit1) echo "boom happened"; echo "All sets applied"; exit 1 ;;
  bang) echo "!! x went wrong"; echo "All sets applied" ;;
  failed) echo "set b FAILED"; echo "All sets applied" ;;
  missing) echo "done, nothing more" ;;
esac
"""

# The fake kirocrew the script must call as VENV/bin/kirocrew. It logs argv to the
# shared calls log and KIROCREW_HOME to its own file; FAKE_KC_FAIL=<word> makes
# the subcommand with that name (uninstall, install, enable) fail.
_FAKE_KIROCREW = r"""#!/bin/bash
echo "kirocrew $*" >> "${FAKE_CALLS_LOG:-/dev/null}"
echo "KIROCREW_HOME=${KIROCREW_HOME-unset}" >> "${FAKE_KC_HOME_LOG:-/dev/null}"
case "$*" in *"app ${FAKE_KC_FAIL:-@@none@@}"*) echo "kirocrew: ${FAKE_KC_FAIL} failed" >&2; exit 1 ;; esac
exit 0
"""

# systemctl: is-active answers "inactive" (exit 3) unless FAKE_ACTIVE=1
_SYSTEMCTL_BODY = r"""case "$*" in
  *" is-active "*) if [ "${FAKE_ACTIVE:-0}" = 1 ]; then exit 0; else exit 3; fi ;;
esac"""

# curl: fails the first FAKE_CURL_FAILS calls (all of them when "always")
_CURL_BODY = r"""f="$(dirname "$0")/curl.count"
n=$(cat "$f" 2>/dev/null || echo 0); n=$((n + 1)); echo "$n" > "$f"
if [ "${FAKE_CURL_FAILS:-0}" = always ] || [ "$n" -le "${FAKE_CURL_FAILS:-0}" ]; then
  echo "curl: (7) Failed to connect" >&2; exit 7
fi"""

_FILES = {
    "app.json": "{}\n",
    "gateway-patches/apply.sh": _FAKE_APPLY,
    "README.md": "one\n",
}


def _build_kiro_crew(root: Path) -> None:
    """A pristine kiro_crew in kc-src and a stale one in the venv's site-packages."""
    src = root / "kc-src" / "src" / "kiro_crew"
    (src / "sub").mkdir(parents=True)
    (src / "__init__.py").write_text("# pristine\n")
    (src / "gateway.py").write_text("pristine gateway\n")
    (src / "sub" / "mod.py").write_text("pristine mod\n")
    site = root / "venv" / "lib" / "site-packages" / "kiro_crew"
    site.mkdir(parents=True)
    (site / "__init__.py").write_text("# patched\n")
    (site / "gateway.py").write_text("patched gateway\n")
    (site / "gateway.py.bak-seta-1").write_text("backup\n")
    (site / "foo.py.bak-setb-1").write_text("stale backup\n")
    (site / "kc_confine.py").write_text("added by a patch set\n")
    (root / "venv" / "bin").mkdir(parents=True)
    py = root / "venv" / "bin" / "python"
    py.write_text(f'#!/bin/bash\nexec "{sys.executable}" "$@"\n')
    py.chmod(0o755)


@pytest.fixture
def fx(sandbox: Sandbox, tmp_path: Path) -> Fx:
    tmp = tmp_path.resolve()
    remote, seed, repo, root = tmp / "remote.git", tmp / "seed", tmp / "repo", tmp / "vroot"
    env = {**sandbox.env(), **_GIT_ENV}

    def g(*args: str) -> None:
        subprocess.run(["git", *args], env=env, check=True, capture_output=True, timeout=60)

    g("init", "-q", "--bare", "-b", "main", str(remote))
    g("init", "-q", "-b", "main", str(seed))
    fx_ = Fx(sandbox, remote, seed, repo, root, "")
    sha = fx_.commit(_FILES, "first")
    g("-C", str(seed), "push", "-q", str(remote), "HEAD:refs/heads/main",
      "HEAD:refs/pull/1/head", "HEAD:refs/heads/feat/x")
    g("clone", "-q", str(remote), str(repo))
    _write_env(root)
    _build_kiro_crew(root)
    kc = root / "venv" / "bin" / "kirocrew"
    kc.write_text(_FAKE_KIROCREW)
    kc.chmod(0o755)
    (root / "home").mkdir()
    (root / "home" / ".env").write_text(
        "SLACK_BOT_TOKEN=xoxb-test-not-real\nSLACK_APP_TOKEN=xapp-test-not-real\n")
    sandbox.stub("systemctl", body=_SYSTEMCTL_BODY)
    sandbox.stub("curl", body=_CURL_BODY)
    sandbox.stub("journalctl", body=f'cat "{tmp}/journal.txt" 2>/dev/null || true')
    fx_ = fx_._replace(sha=sha)
    before = fx_.heads()
    yield fx_
    assert fx_.heads() == before, "the script changed the branches of --repo"


def move_pr(fx: Fx, n: int = 1, files: dict[str, str] | None = None) -> str:
    new = fx.commit(files or {"README.md": f"moved {n}\n"}, "moved")
    fx.git(fx.seed, "push", "-q", "--force", str(fx.remote), f"HEAD:refs/pull/{n}/head")
    return new


# ---- usage ------------------------------------------------------------------


def test_help_exits_0(sandbox: Sandbox) -> None:
    for flag in ("--help", "-h"):
        r = sandbox.run(SCRIPT, flag)
        assert r.returncode == 0
        for word in ("--root", "--pr", "--branch", "--path", "--sets", "--no-restart", "--dry-run"):
            assert word in r.stdout


def test_unknown_option(fx: Fx) -> None:
    r = fx.install("--bogus")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_root_is_required(fx: Fx) -> None:
    r = fx.install("--pr", "1", root=False)
    assert r.returncode == 2
    assert "--root" in r.stderr


def test_unsafe_root(fx: Fx) -> None:
    for bad in ("/", str(fx.sb.home), f"{fx.sb.home}/.kiro/crew/x"):
        r = fx.sb.run(SCRIPT, "--root", bad, "--pr", "1", "--repo", str(fx.repo), "--dry-run")
        assert r.returncode == 2, bad
        assert "!! " in r.stderr


@pytest.mark.parametrize("args", [
    [],
    ["--pr", "1", "--branch", "feat/x"],
    ["--pr", "1", "--path", "."],
    ["--branch", "feat/x", "--path", "."],
    ["--pr", "1", "--branch", "feat/x", "--path", "."],
])
def test_exactly_one_source(fx: Fx, args: list[str]) -> None:
    r = fx.install(*args, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr
    assert not (fx.root / "checkouts").exists()


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "1x", "", "1 2", "01"])
def test_bad_pr(fx: Fx, bad: str) -> None:
    r = fx.install("--pr", bad, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


@pytest.mark.parametrize("bad", ["", "-x", "a..b", "a b", "@{-1}", "x.lock", "/x", "x/"])
def test_bad_branch(fx: Fx, bad: str) -> None:
    r = fx.install("--branch", bad, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


@pytest.mark.parametrize("bad", ["a,", ",a", "a,,b", "A", "a-b", "a b", "", "a;b", "a,B"])
def test_bad_sets(fx: Fx, bad: str) -> None:
    r = fx.install("--pr", "1", "--sets", bad, "--dry-run")
    assert r.returncode == 2
    assert "!! " in r.stderr


def test_bad_remote(fx: Fx) -> None:
    for bad in ("", "-u"):
        r = fx.install("--pr", "1", "--remote", bad, "--dry-run")
        assert r.returncode == 2
        assert "!! " in r.stderr


def test_missing_verify_env(fx: Fx) -> None:
    (fx.root / "verify.env").unlink()
    r = fx.install("--pr", "1", "--dry-run")
    assert r.returncode == 2
    assert f"!! {fx.root}/verify.env not found: run scripts/verify-init.sh --root {fx.root} first" in r.stderr
    assert not (fx.root / "checkouts").exists()


def test_verify_env_for_another_root(fx: Fx) -> None:
    text = (fx.root / "verify.env").read_text().replace(f"ROOT={fx.root}\n", "ROOT=/elsewhere\n")
    (fx.root / "verify.env").write_text(text)
    r = fx.install("--pr", "1", "--dry-run")
    assert r.returncode != 0
    assert "!! " in r.stderr


def test_repo_is_not_a_git_repo(fx: Fx, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    r = fx.sb.run(SCRIPT, "--root", str(fx.root), "--repo", str(plain), "--pr", "1", "--dry-run",
                  **_GIT_ENV)
    assert r.returncode != 0
    assert "!! " in r.stderr


# ---- --pr -------------------------------------------------------------------


def test_pr_creates_detached_checkout(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart")
    d = fx.root / "checkouts" / "pr-1"
    assert fx.head_of(d) == fx.sha
    assert fx.git(d, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0  # detached
    assert f">>> source: pr 1 at {fx.sha[:12]} ({d})" in r.stdout
    assert str(d) in fx.worktrees()
    assert r.returncode == 0, r.stderr
    assert ">>> patched, gateway left stopped (--no-restart)" in r.stdout


def test_pr_rerun_follows_moved_ref(fx: Fx) -> None:
    fx.install("--pr", "1")
    new = move_pr(fx)
    assert new != fx.sha
    r = fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    assert fx.head_of(d) == new
    assert (d / "README.md").read_text() == "moved 1\n"
    assert f"at {new[:12]}" in r.stdout
    assert fx.worktrees().count(str(d)) == 1
    assert r.returncode == 0, r.stderr


def test_pr_rerun_unchanged_is_fine(fx: Fx) -> None:
    fx.install("--pr", "1")
    r = fx.install("--pr", "1")
    assert fx.head_of(fx.root / "checkouts" / "pr-1") == fx.sha
    assert r.returncode == 0, r.stderr


def test_dirty_checkout_is_refused_and_untouched(fx: Fx) -> None:
    fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    (d / "README.md").write_text("my edit\n")
    move_pr(fx)
    r = fx.install("--pr", "1")
    assert r.returncode == 1
    assert "!! " in r.stderr
    assert fx.head_of(d) == fx.sha
    assert (d / "README.md").read_text() == "my edit\n"


def test_untracked_file_counts_as_dirty(fx: Fx) -> None:
    fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    (d / "notes.txt").write_text("x\n")
    move_pr(fx)
    r = fx.install("--pr", "1")
    assert "!! " in r.stderr
    assert (d / "notes.txt").exists()
    assert fx.head_of(d) == fx.sha


def test_other_worktrees_are_untouched(fx: Fx) -> None:
    other = fx.root / "checkouts" / "pr-9"
    fx.root.joinpath("checkouts").mkdir()
    fx.git(fx.repo, "worktree", "add", "--detach", str(other), fx.sha)
    move_pr(fx)
    fx.install("--pr", "1")
    assert fx.head_of(other) == fx.sha
    assert str(other) in fx.worktrees()


def test_existing_dir_that_is_not_a_worktree_is_never_deleted(fx: Fx) -> None:
    d = fx.root / "checkouts" / "pr-1"
    d.mkdir(parents=True)
    (d / "keep.txt").write_text("mine\n")
    r = fx.install("--pr", "1")
    assert r.returncode == 1
    assert "!! " in r.stderr
    assert (d / "keep.txt").read_text() == "mine\n"


def test_worktree_of_another_repo_is_refused(fx: Fx, tmp_path: Path) -> None:
    d = fx.root / "checkouts" / "pr-1"
    d.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(fx.remote), str(d)], env=fx.env(), check=True,
                   capture_output=True)
    r = fx.install("--pr", "1")
    assert r.returncode == 1
    assert "!! " in r.stderr
    assert (d / "app.json").exists()


def test_checkout_without_required_files_is_refused(fx: Fx) -> None:
    fx.git(fx.seed, "checkout", "-q", "--orphan", "bare")
    fx.git(fx.seed, "rm", "-rfq", ".")
    (fx.seed / "x.txt").write_text("x\n")
    fx.git(fx.seed, "add", "-A")
    fx.git(fx.seed, "commit", "-q", "-m", "bare")
    fx.git(fx.seed, "push", "-q", str(fx.remote), "HEAD:refs/pull/2/head")
    r = fx.install("--pr", "2")
    assert r.returncode == 1
    assert "!! " in r.stderr and "app.json" in r.stderr
    assert not (fx.root / "checkouts" / "pr-2").exists()
    assert len(fx.worktrees()) == 1


def test_missing_pr_ref_fails(fx: Fx) -> None:
    r = fx.install("--pr", "77")
    assert r.returncode == 1
    assert "!! " in r.stderr
    assert not (fx.root / "checkouts" / "pr-77").exists()


def test_unknown_remote_fails(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--remote", "nope")
    assert r.returncode == 1
    assert "!! " in r.stderr


# ---- --branch ---------------------------------------------------------------


def test_branch_dir_name_replaces_slashes(fx: Fx) -> None:
    r = fx.install("--branch", "feat/x")
    d = fx.root / "checkouts" / "branch-feat-x"
    assert fx.head_of(d) == fx.sha
    assert f">>> source: branch feat/x at {fx.sha[:12]} ({d})" in r.stdout
    assert fx.git(d, "symbolic-ref", "-q", "HEAD", check=False).returncode != 0
    assert r.returncode == 0, r.stderr


def test_branch_rerun_follows_remote_branch(fx: Fx) -> None:
    fx.install("--branch", "feat/x")
    new = fx.commit({"README.md": "branch moved\n"})
    fx.git(fx.seed, "push", "-q", str(fx.remote), "HEAD:refs/heads/feat/x")
    fx.install("--branch", "feat/x")
    assert fx.head_of(fx.root / "checkouts" / "branch-feat-x") == new


# ---- --path -----------------------------------------------------------------


def _plain_tree(parent: Path) -> Path:
    d = parent / "plain-tree"
    (d / "gateway-patches").mkdir(parents=True)
    (d / "app.json").write_text("{}\n")
    (d / "gateway-patches" / "apply.sh").write_text(_FAKE_APPLY)
    return d


def test_path_git_tree_makes_no_worktree(fx: Fx) -> None:
    r = fx.install("--path", str(fx.repo))
    assert f">>> source: path {fx.repo} at {fx.sha[:12]} ({fx.repo})" in r.stdout
    assert not (fx.root / "checkouts").exists()
    assert fx.worktrees() == [str(fx.repo)]
    assert "DIRTY" not in r.stdout + r.stderr
    assert r.returncode == 0, r.stderr


def test_path_dirty_is_reported(fx: Fx) -> None:
    (fx.repo / "README.md").write_text("edited\n")
    r = fx.install("--path", str(fx.repo))
    assert "DIRTY=1" in r.stdout + r.stderr
    assert (fx.repo / "README.md").read_text() == "edited\n"
    assert r.returncode == 0, r.stderr


def test_path_without_git_is_unknown(fx: Fx, tmp_path: Path) -> None:
    d = _plain_tree(tmp_path)
    r = fx.install("--path", str(d))
    assert "at unknown" in r.stdout
    assert r.returncode == 0, r.stderr
    assert not (fx.root / "checkouts").exists()


@pytest.mark.parametrize("missing", ["app.json", "gateway-patches/apply.sh"])
def test_path_requires_the_files(fx: Fx, tmp_path: Path, missing: str) -> None:
    d = _plain_tree(tmp_path)
    (d / missing).unlink()
    r = fx.install("--path", str(d))
    assert r.returncode != 0
    assert "!! " in r.stderr


def test_path_must_exist(fx: Fx, tmp_path: Path) -> None:
    r = fx.install("--path", str(tmp_path / "nope"))
    assert r.returncode != 0
    assert "!! " in r.stderr


# ---- --dry-run --------------------------------------------------------------


def test_dry_run_pr_fetches_but_creates_nothing(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--dry-run")
    assert r.returncode == 0, r.stderr
    assert f">>> source: pr 1 at {fx.sha[:12]} ({fx.root}/checkouts/pr-1)" in r.stdout
    assert not (fx.root / "checkouts").exists()
    assert fx.worktrees() == [str(fx.repo)]
    plan = [ln for ln in r.stdout.splitlines() if ln.startswith("[dry-run] ")]
    text = "\n".join(plan)
    assert "git -C" in text and "worktree add" in text
    for word in ("stop", "kiro_crew", "apply.sh", "reinstall", "start", "health", "journal",
                 "state"):
        assert word in text, word
    assert "--only" not in text
    assert "later steps are not implemented" not in r.stdout


def test_dry_run_sets_and_no_restart(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--dry-run", "--sets", "b,k", "--no-restart")
    assert r.returncode == 0
    assert "--only b,k" in r.stdout
    assert "--no-restart" in r.stdout


def test_dry_run_sees_moved_ref_and_leaves_checkout(fx: Fx) -> None:
    fx.install("--pr", "1")
    new = move_pr(fx)
    r = fx.install("--pr", "1", "--dry-run")
    assert r.returncode == 0
    assert f"at {new[:12]}" in r.stdout
    assert fx.head_of(fx.root / "checkouts" / "pr-1") == fx.sha


def test_dry_run_path(fx: Fx) -> None:
    r = fx.install("--path", str(fx.repo), "--dry-run")
    assert r.returncode == 0
    assert not (fx.root / "checkouts").exists()


def test_dry_run_rejects_dirty_checkout(fx: Fx) -> None:
    fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    (d / "README.md").write_text("edit\n")
    r = fx.install("--pr", "1", "--dry-run")
    assert r.returncode == 1
    assert "!! " in r.stderr


# ---- default --repo ---------------------------------------------------------


def test_default_repo_is_the_toplevel_of_the_scripts_dir(fx: Fx) -> None:
    """Copy the scripts into the clone and run them from there, without --repo."""
    shutil.copytree(SCRIPTS, fx.repo / "scripts")
    r = subprocess.run(
        [str(fx.sb.tools / "bash"), str(fx.repo / "scripts" / SCRIPT), "--root", str(fx.root),
         "--pr", "1", "--dry-run"],
        env=fx.env(), capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    assert r.returncode == 0, r.stderr
    assert f"at {fx.sha[:12]}" in r.stdout
    assert fx.git(fx.repo, "rev-parse", "FETCH_HEAD").stdout.strip() == fx.sha


def test_all_runs_leave_no_stray_files_outside_root(fx: Fx) -> None:
    fx.install("--pr", "1")
    fx.install("--branch", "feat/x")
    assert sorted(p.name for p in (fx.root / "checkouts").iterdir()) == ["branch-feat-x", "pr-1"]
    assert not list(fx.sb.home.rglob("*"))  # HOME untouched
    assert os.path.isfile(fx.root / "verify.env")


# ---- reset and apply --------------------------------------------------------


def _tree(d: Path) -> dict[str, str]:
    return {str(p.relative_to(d)): p.read_text() for p in sorted(d.rglob("*")) if p.is_file()}


def _apply_extra(fx: Fx, mode: str = "ok") -> dict[str, str]:
    return {"FAKE_APPLY_LOG": str(fx.apply_log), "FAKE_APPLY_MODE": mode}


def test_reset_replaces_site_with_the_pristine_tree(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert not (fx.site / "foo.py.bak-setb-1").exists()
    assert not (fx.site / "gateway.py.bak-seta-1").exists()
    assert not (fx.site / "kc_confine.py").exists()
    assert _tree(fx.site) == _tree(fx.src_pkg)
    assert not list(fx.site.parent.glob("*.verify-new.*"))


def test_stale_files_are_gone_before_apply_runs(fx: Fx) -> None:
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert "stale_present=0" in fx.apply_log.read_text()
    assert "stale_present=1" not in fx.apply_log.read_text()


def test_reset_makes_the_copy_writable(fx: Fx) -> None:
    for p in fx.src_pkg.rglob("*.py"):
        p.chmod(0o444)
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert all(os.access(p, os.W_OK) for p in fx.site.rglob("*") if p.is_file())


def test_reset_creates_a_missing_site(fx: Fx) -> None:
    shutil.rmtree(fx.site)
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert _tree(fx.site) == _tree(fx.src_pkg)


def test_systemctl_stop_is_called_for_the_unit(fx: Fx) -> None:
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert "--user stop kirocrew-verify-verify.service" in fx.sb.calls("systemctl")
    assert not [c for c in fx.sb.calls("systemctl") if " start " in f" {c} "]


def test_stop_runs_before_the_reset(fx: Fx) -> None:
    # systemctl stub records, at call time, whether the stale file still exists
    fx.sb.stub("systemctl", body=f'ls "{fx.site}" >> "{fx.sb.tmp}/at-stop.txt"\n{_SYSTEMCTL_BODY}')
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert "foo.py.bak-setb-1" in (fx.sb.tmp / "at-stop.txt").read_text()


def test_stop_exit_5_means_not_loaded_and_is_a_warning(fx: Fx) -> None:
    fx.sb.stub("systemctl", exit_code=5, body='echo "Unit not loaded." >&2')
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert "-- warning:" in r.stderr and "not loaded" in r.stderr
    assert _tree(fx.site) == _tree(fx.src_pkg)


def test_stop_failure_is_fatal_and_nothing_is_reset(fx: Fx) -> None:
    fx.sb.stub("systemctl", exit_code=1, body='echo "Failed to connect to bus" >&2')
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "!! " in r.stderr and "kirocrew-verify-verify.service" in r.stderr
    assert (fx.site / "foo.py.bak-setb-1").exists()
    assert fx.applies() == []


def test_apply_runs_twice_with_no_only_by_default(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert fx.applies() == ["argv: ", "argv: "]


def test_apply_gets_only_with_sets(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", "--sets", "b,k", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert fx.applies() == ["argv: --only b,k", "argv: --only b,k"]


def test_apply_env_has_site_override_and_python(fx: Fx) -> None:
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    text = fx.apply_log.read_text()
    assert text.count(f"KC_SITE_OVERRIDE={fx.site}\n") == 2
    assert text.count(f"KC_PYTHON={fx.root}/venv/bin/python\n") == 2


def test_apply_runs_the_script_of_the_checkout(fx: Fx) -> None:
    fx.commit({"gateway-patches/apply.sh": _FAKE_APPLY + "echo from-new-checkout\n"}, "new")
    fx.git(fx.seed, "push", "-q", "--force", str(fx.remote), "HEAD:refs/pull/1/head")
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert fx.logs()[0].read_text().count("from-new-checkout") == 2


def test_log_has_a_header_per_run_and_the_output(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", "--sets", "b", extra=_apply_extra(fx))
    logs = fx.logs()
    assert len(logs) == 1
    assert logs[0].name.startswith("apply-") and logs[0].name.endswith("Z.log")
    stamp = logs[0].name[len("apply-"):-len(".log")]
    assert len(stamp) == 16 and stamp[8] == "T" and stamp[-1] == "Z"
    text = logs[0].read_text()
    heads = [ln for ln in text.splitlines() if ln.startswith("=== apply.sh ")]
    assert len(heads) == 2
    assert heads[0].startswith("=== apply.sh first run: ") and heads[0].endswith(" ===")
    assert heads[1].startswith("=== apply.sh rerun run: ") and heads[1].endswith(" ===")
    assert "--only b" in heads[0]
    assert text.count("All sets applied") == 2
    assert str(logs[0]) in r.stdout


def test_no_restart_reports_sha_sets_and_log(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", "--sets", "b,k", extra=_apply_extra(fx))
    assert r.returncode == 0
    after = r.stdout.split(">>> patched, gateway left stopped (--no-restart)")[1]
    assert fx.sha in after or fx.sha[:12] in after
    assert "b,k" in after
    assert str(fx.logs()[0]) in after


def test_no_restart_default_sets_say_all(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    after = r.stdout.split(">>> patched, gateway left stopped (--no-restart)")[1]
    assert "all" in after


@pytest.mark.parametrize("mode", ["anchors", "exit1", "bang", "failed", "missing"])
def test_apply_failure_variants_fail_the_first_run(fx: Fx, mode: str) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx, mode))
    assert r.returncode == 1
    logs = fx.logs()
    assert len(logs) == 1
    assert (f"!! apply.sh failed on the first run, full log: {logs[0]}") in r.stderr
    assert len(fx.applies()) == 1  # the rerun never starts
    assert "=== apply.sh first run: " in logs[0].read_text()
    assert ">>> patched" not in r.stdout
    assert not [c for c in fx.sb.calls("systemctl") if " start " in f" {c} "]


@pytest.mark.parametrize("mode", ["anchors", "exit1", "bang", "failed", "missing"])
def test_apply_failure_variants_fail_the_rerun(fx: Fx, mode: str) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx, f"second-{mode}"))
    assert r.returncode == 1
    assert "!! apply.sh failed on the rerun run, full log: " in r.stderr
    assert len(fx.applies()) == 2
    text = fx.logs()[0].read_text()
    assert "=== apply.sh first run: " in text and "=== apply.sh rerun run: " in text


def test_failure_prints_only_the_last_40_lines(fx: Fx) -> None:
    noisy = _FAKE_APPLY + 'for i in {1..80}; do echo "noise line $i"; done\n'
    fx.commit({"gateway-patches/apply.sh": noisy}, "noisy")
    fx.git(fx.seed, "push", "-q", "--force", str(fx.remote), "HEAD:refs/pull/1/head")
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx, "bang"))
    assert r.returncode == 1
    assert "noise line 80" in r.stderr and "noise line 41" in r.stderr
    assert "noise line 40" not in r.stderr


def test_failure_tail_is_from_the_failing_run_only(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx, "second-exit1"))
    assert "boom happened" in r.stderr
    # the first (good) run printed "applying"; the tail comes from the second run only
    assert "applying" not in r.stderr


def test_failure_leaves_the_gateway_stopped_and_site_patched_state(fx: Fx) -> None:
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx, "exit1"))
    assert fx.sb.calls("systemctl") == ["--user stop kirocrew-verify-verify.service"]
    assert _tree(fx.site) == _tree(fx.src_pkg)  # the reset happened, nothing else


@pytest.mark.parametrize("what", ["outside", "other-name", "no-site-packages", "equals-venv",
                                  "not-under-venv-by-prefix"])
def test_site_outside_the_venv_is_refused_and_nothing_is_deleted(
        fx: Fx, tmp_path: Path, what: str) -> None:
    if what == "outside":
        target = tmp_path / "elsewhere" / "site-packages" / "kiro_crew"
    elif what == "other-name":
        target = fx.root / "venv" / "lib" / "site-packages" / "other"
    elif what == "no-site-packages":
        target = fx.root / "venv" / "lib" / "kiro_crew"
    elif what == "equals-venv":
        target = fx.root / "venv"
    else:  # a sibling whose name only starts with the venv's name
        target = fx.root / "venv2" / "lib" / "site-packages" / "kiro_crew"
    target.mkdir(parents=True, exist_ok=True)
    (target / "precious.txt").write_text("keep\n")
    fx.write_env(KC_SITE=str(target))
    before_venv = _tree(fx.root / "venv")
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "!! " in r.stderr
    assert (target / "precious.txt").read_text() == "keep\n"
    assert _tree(fx.root / "venv") == before_venv
    assert fx.applies() == []


@pytest.mark.parametrize("via", ["plain", "symlinked-venv"])
def test_venv_outside_root_is_refused_and_nothing_is_deleted(
        fx: Fx, tmp_path: Path, via: str) -> None:
    """A verify.env that points VENV and KC_SITE away from --root is never reset."""
    other = tmp_path / "other-venv"
    site = other / "lib" / "site-packages" / "kiro_crew"
    site.mkdir(parents=True)
    (site / "precious.txt").write_text("keep\n")
    if via == "plain":
        fx.write_env(VENV=str(other), KC_SITE=str(site))
    else:  # a venv inside the root that is a link to one outside it
        link = fx.root / "linked-venv"
        link.symlink_to(other)
        fx.write_env(VENV=str(link), KC_SITE=str(link / "lib" / "site-packages" / "kiro_crew"))
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "!! refusing to reset: the venv" in r.stderr and "is not inside" in r.stderr
    assert (site / "precious.txt").read_text() == "keep\n"
    assert not list(other.rglob("*.verify-new.*"))
    assert fx.applies() == []


@pytest.mark.parametrize("what", ["outside-root", "other-name", "missing-pristine"])
def test_refused_reset_does_not_stop_the_gateway(fx: Fx, tmp_path: Path, what: str) -> None:
    if what == "outside-root":
        other = tmp_path / "other-venv"
        (other / "lib" / "site-packages" / "kiro_crew").mkdir(parents=True)
        fx.write_env(VENV=str(other), KC_SITE=str(other / "lib" / "site-packages" / "kiro_crew"))
    elif what == "other-name":
        fx.write_env(KC_SITE=str(fx.root / "venv" / "lib" / "site-packages" / "other"))
    else:
        (fx.src_pkg / "__init__.py").unlink()
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1 and "!! " in r.stderr
    assert fx.sb.calls("systemctl") == []


def test_site_that_is_a_symlink_is_refused(fx: Fx, tmp_path: Path) -> None:
    real = tmp_path / "real-kiro-crew"
    real.mkdir()
    (real / "precious.txt").write_text("keep\n")
    shutil.rmtree(fx.site)
    fx.site.symlink_to(real)
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1 and "!! " in r.stderr
    assert (real / "precious.txt").read_text() == "keep\n"
    assert fx.site.is_symlink()
    assert fx.applies() == []


def test_symlinked_parent_that_leaves_the_venv_is_refused(fx: Fx, tmp_path: Path) -> None:
    outside = tmp_path / "outside-sp"
    (outside / "kiro_crew").mkdir(parents=True)
    (outside / "kiro_crew" / "precious.txt").write_text("keep\n")
    shutil.rmtree(fx.site.parent)
    fx.site.parent.symlink_to(outside)
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1 and "!! " in r.stderr
    assert (outside / "kiro_crew" / "precious.txt").read_text() == "keep\n"


@pytest.mark.parametrize("drop", ["init", "dir"])
def test_pristine_tree_must_hold_init(fx: Fx, drop: str) -> None:
    if drop == "init":
        (fx.src_pkg / "__init__.py").unlink()
    else:
        shutil.rmtree(fx.src_pkg)
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 1 and "!! " in r.stderr and "__init__.py" in r.stderr
    assert (fx.site / "foo.py.bak-setb-1").exists()
    assert fx.applies() == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes")
def test_failed_copy_keeps_the_old_site_and_leaves_no_temp_dir(fx: Fx) -> None:
    unreadable = fx.src_pkg / "sub" / "secret.py"
    unreadable.write_text("x\n")
    unreadable.chmod(0)
    try:
        r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    finally:
        unreadable.chmod(0o644)
    assert r.returncode == 1 and "!! " in r.stderr
    assert (fx.site / "foo.py.bak-setb-1").exists()
    assert (fx.site / "gateway.py").read_text() == "patched gateway\n"
    assert not list(fx.site.parent.glob("*.verify-new.*"))
    assert fx.applies() == []


def test_dry_run_stops_resets_and_applies_nothing(fx: Fx) -> None:
    before = _tree(fx.site)
    r = fx.install("--pr", "1", "--dry-run", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert _tree(fx.site) == before
    assert fx.sb.calls("systemctl") == []
    assert fx.applies() == []
    assert not (fx.root / "logs").exists()
    assert "[dry-run] 1. stop: systemctl --user stop kirocrew-verify-verify.service" in r.stdout


def test_path_source_is_applied_from_in_place(fx: Fx) -> None:
    r = fx.install("--path", str(fx.repo), "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert len(fx.applies()) == 2
    assert fx.git(fx.repo, "status", "--porcelain").stdout == ""  # nothing written into it


def test_second_install_resets_a_previously_patched_site(fx: Fx) -> None:
    fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    (fx.site / "gateway.py").write_text("patched again\n")
    (fx.site / "foo.py.bak-setb-2").write_text("backup\n")
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert _tree(fx.site) == _tree(fx.src_pkg)
    assert len(fx.logs()) >= 1


# ---- app reinstall, start, health, journal, state, summary -------------------

UNIT = "kirocrew-verify-verify.service"
APP = "slack-channels-onboard"


def _install_app_dir(fx: Fx) -> None:
    fx.app_dir.mkdir(parents=True)


def _tags(fx: Fx) -> list[str]:
    """The stub calls reduced to the steps the order test cares about."""
    out = []
    for ln in fx.calls_log():
        if ln.startswith("curl "):
            out.append("curl")
        elif ln.startswith("journalctl "):
            out.append("journalctl")
        else:
            out.append(ln)
    return out


def test_command_order_with_an_installed_app(fx: Fx) -> None:
    _install_app_dir(fx)
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    d = fx.root / "checkouts" / "pr-1"
    assert _tags(fx) == [
        f"systemctl --user stop {UNIT}",
        "apply.sh ",
        "apply.sh ",
        f"systemctl --user is-active --quiet {UNIT}",
        f"kirocrew app uninstall {APP}",
        f"kirocrew app install {d}",
        f"kirocrew app enable {APP}",
        f"systemctl --user start {UNIT}",
        "curl",
        "journalctl",
    ]


def test_no_uninstall_when_the_app_is_not_installed(fx: Fx) -> None:
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    kc = [c for c in _tags(fx) if c.startswith("kirocrew ")]
    assert kc == [f"kirocrew app install {fx.root / 'checkouts' / 'pr-1'}",
                  f"kirocrew app enable {APP}"]


def test_every_kirocrew_call_uses_the_verify_home(fx: Fx) -> None:
    _install_app_dir(fx)
    fx.install("--pr", "1", extra=_apply_extra(fx))
    homes = fx.kc_home_log.read_text().splitlines()
    assert homes == [f"KIROCREW_HOME={fx.root}/home"] * 3


def test_path_source_installs_the_given_dir(fx: Fx) -> None:
    r = fx.install("--path", str(fx.repo), extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert f"kirocrew app install {fx.repo.resolve()}" in fx.calls_log()


def test_start_curl_and_journal_arguments(fx: Fx) -> None:
    fx.install("--pr", "1", extra=_apply_extra(fx))
    assert fx.sb.calls("curl")[0] == "-fsS -o /dev/null --max-time 3 http://127.0.0.1:8790/api/health"
    (j,) = fx.sb.calls("journalctl")
    m = re.fullmatch(rf"--user -u {UNIT} --since (\d{{4}}-\d\d-\d\d \d\d:\d\d:\d\d) "
                     r"--no-pager -o cat", j)
    assert m, j


@pytest.mark.parametrize("which", ["uninstall", "install", "enable"])
def test_app_step_failure_is_fatal_and_nothing_starts(fx: Fx, which: str) -> None:
    _install_app_dir(fx)
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), "FAKE_KC_FAIL": which})
    assert r.returncode == 1
    assert "!! " in r.stderr and which in r.stderr
    tags = _tags(fx)
    assert f"systemctl --user start {UNIT}" not in tags
    assert "curl" not in tags and "journalctl" not in tags
    assert not fx.state.exists()


def test_app_step_refuses_a_running_unit(fx: Fx) -> None:
    _install_app_dir(fx)
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), "FAKE_ACTIVE": "1"})
    assert r.returncode == 1
    assert "!! " in r.stderr and UNIT in r.stderr and "active" in r.stderr
    assert not [c for c in _tags(fx) if c.startswith("kirocrew ")]
    assert f"systemctl --user start {UNIT}" not in _tags(fx)


def test_start_failure_is_fatal(fx: Fx) -> None:
    fx.sb.stub("systemctl", body=_SYSTEMCTL_BODY +
               '\ncase "$*" in *" start "*) echo "Job failed" >&2; exit 1 ;; esac')
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "!! " in r.stderr and "start" in r.stderr
    assert "curl" not in _tags(fx) and not fx.state.exists()


def test_health_retries_until_it_answers(fx: Fx) -> None:
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), "FAKE_CURL_FAILS": "2"})
    assert r.returncode == 0, r.stderr
    assert len(fx.sb.calls("curl")) == 3


def test_health_timeout_fails_shows_the_journal_and_leaves_the_gateway_running(fx: Fx) -> None:
    fx.journal.write_text("line one of the journal\nline two of the journal\n")
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), "FAKE_CURL_FAILS": "always"})
    assert r.returncode == 1
    assert "!! " in r.stderr and "health" in r.stderr
    assert "running" in r.stderr
    assert f"journalctl --user -u {UNIT} -f" in r.stderr
    assert "line two of the journal" in r.stdout + r.stderr
    assert any(c.startswith(f"--user -u {UNIT} -n 40 ") for c in fx.sb.calls("journalctl"))
    assert len(fx.sb.calls("curl")) >= 2
    assert not any(" stop " in f" {c} " for c in fx.sb.calls("systemctl")[1:])
    assert not fx.state.exists()


def test_journal_traceback_fails_and_prints_the_line(fx: Fx) -> None:
    fx.journal.write_text("all fine\nTraceback (most recent call last):\n  boom\nfine again\n")
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "Traceback (most recent call last):" in r.stdout + r.stderr
    assert "!! " in r.stderr and "running" in r.stderr
    assert not fx.state.exists()


@pytest.mark.parametrize("line", [
    "slack-channels-onboard: ERROR cannot start",
    "slack_channels_onboard failed to load",
    "Slack-Channels-Onboard raised an Exception",
    "app slack-channels-onboard: some error happened",
])
def test_journal_app_error_lines_fail(fx: Fx, line: str) -> None:
    fx.journal.write_text(f"ok\n{line}\n")
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert line in r.stdout + r.stderr


@pytest.mark.parametrize("line", [
    "slack: some other app printed an error",
    "kiro_crew.slack: failed to fetch channel list",
    "slack-channels-onboard: loaded 3 channels",
    "a traceback in lower case without the app",
    "slack-channels-onboard: traceback lower case only",
])
def test_journal_unrelated_lines_pass(fx: Fx, line: str) -> None:
    fx.journal.write_text(f"{line}\n")
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr


def test_journal_prints_at_most_40_matching_lines(fx: Fx) -> None:
    fx.journal.write_text("".join(f"Traceback number {i}\n" for i in range(100)))
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert (r.stdout + r.stderr).count("Traceback number") == 40


def test_journal_failure_is_fatal_and_leaves_the_gateway_running(fx: Fx) -> None:
    fx.sb.stub("journalctl", exit_code=1, body='echo "No journal files were found." >&2')
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert "!! " in r.stderr and "journal" in r.stderr and "running" in r.stderr
    assert not fx.state.exists()


def test_settle_wait_happens_before_the_journal_scan(fx: Fx) -> None:
    # the journalctl stub records when it ran; the curl stub when it answered
    fx.sb.stub("curl", body=_CURL_BODY + f'\ndate +%s.%N > "{fx.sb.tmp}/t-curl"')
    fx.sb.stub("journalctl", body=f'date +%s.%N > "{fx.sb.tmp}/t-journal"')
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), "VERIFY_SETTLE_SECS": "1"})
    assert r.returncode == 0, r.stderr
    gap = float((fx.sb.tmp / "t-journal").read_text()) - float((fx.sb.tmp / "t-curl").read_text())
    assert gap >= 1.0, gap


@pytest.mark.parametrize("name,value", [
    ("VERIFY_HEALTH_TIMEOUT", "abc"), ("VERIFY_HEALTH_TIMEOUT", "-1"),
    ("VERIFY_SETTLE_SECS", "1.5"), ("VERIFY_HEALTH_INTERVAL", "x"),
    ("VERIFY_HEALTH_INTERVAL", "0"),
])
def test_bad_timing_env_is_a_usage_error_before_anything_runs(fx: Fx, name: str, value: str) -> None:
    r = fx.install("--pr", "1", extra={**_apply_extra(fx), name: value})
    assert r.returncode == 2
    assert "!! " in r.stderr and name in r.stderr
    assert fx.sb.calls("systemctl") == []


def test_state_file_fields(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--sets", "b,k", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    st = json.loads(fx.state.read_text())
    assert st["source"] == "pr" and st["id"] == "1"
    assert st["sha"] == fx.sha
    assert st["dirty"] is False
    assert st["sets"] == ["b", "k"]
    assert st["checkout"] == str(fx.root / "checkouts" / "pr-1")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", st["applied_at"])
    assert st["unit"] == UNIT and st["port"] == 8790
    assert st["apply_log"] == str(fx.logs()[0])
    assert st["started"] is True
    assert not list(fx.state.parent.glob("*.tmp*"))


def test_state_sets_say_all_by_default(fx: Fx) -> None:
    fx.install("--branch", "feat/x", extra=_apply_extra(fx))
    st = json.loads(fx.state.read_text())
    assert st["sets"] == "all"
    assert st["source"] == "branch" and st["id"] == "feat/x"


def test_state_for_a_dirty_path_source(fx: Fx) -> None:
    (fx.repo / "README.md").write_text("changed\n")
    r = fx.install("--path", str(fx.repo), extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    st = json.loads(fx.state.read_text())
    assert st["source"] == "path" and st["id"] == str(fx.repo.resolve())
    assert st["dirty"] is True


def test_state_is_replaced_by_the_next_run(fx: Fx) -> None:
    fx.install("--pr", "1", extra=_apply_extra(fx))
    fx.install("--branch", "feat/x", "--sets", "b", extra=_apply_extra(fx))
    st = json.loads(fx.state.read_text())
    assert st["source"] == "branch" and st["sets"] == ["b"]


def test_state_values_are_not_interpreted(fx: Fx) -> None:
    # a --path with quotes and a dollar sign must come out verbatim
    odd = fx.sb.tmp / "odd '\"$(x)` dir"
    shutil.copytree(fx.repo, odd, ignore=shutil.ignore_patterns(".git"))
    r = fx.install("--path", str(odd), extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    st = json.loads(fx.state.read_text())
    assert st["id"] == str(odd.resolve()) and st["checkout"] == str(odd.resolve())


def test_summary_has_the_commands_and_no_tokens(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--sets", "b,k", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert fx.sha in out
    assert "b,k" in out
    assert str(fx.root / "checkouts" / "pr-1") in out
    assert "http://127.0.0.1:8790/" in out
    assert f"journalctl --user -u {UNIT} -f" in out
    assert f"KIROCREW_HOME={fx.root}/home {fx.root}/venv/bin/kirocrew token" in out
    assert "none configured" in out
    assert "gateway left stopped" not in out
    for text in (r.stdout, r.stderr):
        assert "xoxb-" not in text and "xapp-" not in text
    assert [c for c in _tags(fx) if " token" in c] == []


def test_summary_names_the_admin_env_file(fx: Fx) -> None:
    fx.write_env(ADMIN_ENV_FILE=str(fx.root / "admins.env"))
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    assert str(fx.root / "admins.env") in r.stdout
    assert "none configured" not in r.stdout


def test_failure_output_has_no_tokens(fx: Fx) -> None:
    fx.journal.write_text("Traceback\n")
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    for text in (r.stdout, r.stderr):
        assert "xoxb-" not in text and "xapp-" not in text


def test_no_restart_runs_the_app_step_but_does_not_start(fx: Fx) -> None:
    _install_app_dir(fx)
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    d = fx.root / "checkouts" / "pr-1"
    assert _tags(fx) == [
        f"systemctl --user stop {UNIT}",
        "apply.sh ",
        "apply.sh ",
        f"systemctl --user is-active --quiet {UNIT}",
        f"kirocrew app uninstall {APP}",
        f"kirocrew app install {d}",
        f"kirocrew app enable {APP}",
    ]
    assert fx.sb.calls("curl") == [] and fx.sb.calls("journalctl") == []


def test_no_restart_writes_state_with_started_false(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra=_apply_extra(fx))
    assert r.returncode == 0, r.stderr
    st = json.loads(fx.state.read_text())
    assert st["started"] is False
    assert st["sha"] == fx.sha and st["sets"] == "all"
    assert "health" not in r.stdout.lower()
    assert "http://127.0.0.1:8790/" in r.stdout
    assert f"KIROCREW_HOME={fx.root}/home {fx.root}/venv/bin/kirocrew token" in r.stdout
    assert "xoxb-" not in r.stdout + r.stderr


def test_no_restart_app_failure_is_fatal(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--no-restart", extra={**_apply_extra(fx), "FAKE_KC_FAIL": "install"})
    assert r.returncode == 1 and "!! " in r.stderr
    assert not fx.state.exists()


def test_apply_failure_runs_no_app_step(fx: Fx) -> None:
    fx.install("--pr", "1", extra=_apply_extra(fx, "exit1"))
    assert not [c for c in _tags(fx) if c.startswith("kirocrew ")]
    assert not fx.state.exists()


def test_dry_run_plan_is_numbered_1_to_9(fx: Fx) -> None:
    r = fx.install("--pr", "1", "--dry-run")
    nums = [ln.split(".")[0].removeprefix("[dry-run] ") for ln in r.stdout.splitlines()
            if re.match(r"\[dry-run\] \d+\. ", ln)]
    assert nums == [str(i) for i in range(1, 10)]
    assert fx.sb.calls("kirocrew") == [] and not fx.state.exists()
