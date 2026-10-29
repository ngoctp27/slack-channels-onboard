"""Tests for scripts/verify-install.sh: argument handling and source selection.

A bare "remote" in tmp_path carries a commit on refs/pull/1/head and a branch
feat/x; a local clone of it is the --repo. Git runs with an isolated config
(tmp HOME, no system config, placeholder identity). No network is used.

Until Task 6 lands, a real (non-dry) run without --no-restart ends with
"!! not implemented yet: app + restart (Task 6)" after the reset and apply
steps; the source tests below accept that exit and assert the checkout state
instead. The reset and apply steps run against a fake venv, a fake pristine
Kiro Crew tree and a fake gateway-patches/apply.sh that logs its argv and env.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest

from conftest import SCRIPTS, Sandbox

SCRIPT = "verify-install.sh"
NOT_YET = "!! not implemented yet: app + restart (Task 6)"
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
        return self.sb.run(SCRIPT, *full, *args, **_GIT_ENV, **(extra or {}))

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
    (root / "venv" / "bin" / "python").write_text("#!/bin/sh\n")


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
    assert NOT_YET in r.stderr


def test_pr_rerun_unchanged_is_fine(fx: Fx) -> None:
    fx.install("--pr", "1")
    r = fx.install("--pr", "1")
    assert fx.head_of(fx.root / "checkouts" / "pr-1") == fx.sha
    assert NOT_YET in r.stderr


def test_dirty_checkout_is_refused_and_untouched(fx: Fx) -> None:
    fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    (d / "README.md").write_text("my edit\n")
    move_pr(fx)
    r = fx.install("--pr", "1")
    assert r.returncode == 1
    assert "!! " in r.stderr and NOT_YET not in r.stderr
    assert fx.head_of(d) == fx.sha
    assert (d / "README.md").read_text() == "my edit\n"


def test_untracked_file_counts_as_dirty(fx: Fx) -> None:
    fx.install("--pr", "1")
    d = fx.root / "checkouts" / "pr-1"
    (d / "notes.txt").write_text("x\n")
    move_pr(fx)
    r = fx.install("--pr", "1")
    assert "!! " in r.stderr and NOT_YET not in r.stderr
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
    assert "!! " in r.stderr and NOT_YET not in r.stderr
    assert (d / "keep.txt").read_text() == "mine\n"


def test_worktree_of_another_repo_is_refused(fx: Fx, tmp_path: Path) -> None:
    d = fx.root / "checkouts" / "pr-1"
    d.parent.mkdir(parents=True)
    subprocess.run(["git", "clone", "-q", str(fx.remote), str(d)], env=fx.env(), check=True,
                   capture_output=True)
    r = fx.install("--pr", "1")
    assert r.returncode == 1
    assert "!! " in r.stderr and NOT_YET not in r.stderr
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
    assert NOT_YET in r.stderr


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
    assert NOT_YET in r.stderr


def test_path_dirty_is_reported(fx: Fx) -> None:
    (fx.repo / "README.md").write_text("edited\n")
    r = fx.install("--path", str(fx.repo))
    assert "DIRTY=1" in r.stdout + r.stderr
    assert (fx.repo / "README.md").read_text() == "edited\n"
    assert NOT_YET in r.stderr


def test_path_without_git_is_unknown(fx: Fx, tmp_path: Path) -> None:
    d = _plain_tree(tmp_path)
    r = fx.install("--path", str(d))
    assert "at unknown" in r.stdout
    assert NOT_YET in r.stderr
    assert not (fx.root / "checkouts").exists()


@pytest.mark.parametrize("missing", ["app.json", "gateway-patches/apply.sh"])
def test_path_requires_the_files(fx: Fx, tmp_path: Path, missing: str) -> None:
    d = _plain_tree(tmp_path)
    (d / missing).unlink()
    r = fx.install("--path", str(d))
    assert r.returncode != 0
    assert "!! " in r.stderr and NOT_YET not in r.stderr


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
    assert NOT_YET not in r.stderr
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
    fx.sb.stub("systemctl", body=f'ls "{fx.site}" >> "{fx.sb.tmp}/at-stop.txt"')
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


def test_without_no_restart_the_run_ends_at_task_6(fx: Fx) -> None:
    r = fx.install("--pr", "1", extra=_apply_extra(fx))
    assert r.returncode == 1
    assert NOT_YET in r.stderr
    assert len(fx.applies()) == 2  # patched before it gives up


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
