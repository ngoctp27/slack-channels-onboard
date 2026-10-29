"""Tests for scripts/verify-install.sh: argument handling and source selection.

A bare "remote" in tmp_path carries a commit on refs/pull/1/head and a branch
feat/x; a local clone of it is the --repo. Git runs with an isolated config
(tmp HOME, no system config, placeholder identity). No network is used.

Until Task 5 lands, a real (non-dry) run ends with "!! not implemented yet"
after the source step; the tests below accept that exit and assert the
checkout state instead.
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
NOT_YET = "!! not implemented yet"
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

    def install(self, *args: str, repo: bool = True, root: bool = True) -> subprocess.CompletedProcess:
        full: list[str] = []
        if root:
            full += ["--root", str(self.root)]
        if repo:
            full += ["--repo", str(self.repo)]
        return self.sb.run(SCRIPT, *full, *args, **_GIT_ENV)

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


def _write_env(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    kv = {
        "VERIFY_FORMAT": "1", "ROOT": str(root), "NAME": "verify", "PORT": "8790",
        "KC_REF": "v0.10.0", "KC_SRC": f"{root}/kc-src", "VENV": f"{root}/venv",
        "KC_SITE": f"{root}/venv/lib/site-packages/kiro_crew",
        "KIROCREW_HOME": f"{root}/home", "UNIT": "kirocrew-verify-verify.service",
        "UNIT_FILE": f"{root}/unit.service", "ADMIN_ENV_FILE": "",
    }
    (root / "verify.env").write_text("".join(f"{k}={v}\n" for k, v in kv.items()))


_FILES = {
    "app.json": "{}\n",
    "gateway-patches/apply.sh": "#!/bin/sh\necho ok\n",
    "README.md": "one\n",
}


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
    assert r.returncode == 1 and NOT_YET in r.stderr


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
    (d / "gateway-patches" / "apply.sh").write_text("#!/bin/sh\n")
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
