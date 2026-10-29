#!/usr/bin/env bash
# verify-install.sh - put a feature branch or PR of this app on the separate Kiro
# Crew "verify" gateway that verify-init.sh set up.
#
# Repeatable: every run takes the source, checks it out under --root, resets the
# verify gateway's kiro_crew package, applies the gateway patches and reinstalls
# the app. Only the source step exists so far (Task 4 of the plan): a real run
# ends with "!! not implemented yet" once the checkout is in place.
#
# Usage:
#   scripts/verify-install.sh --root DIR (--pr N | --branch B | --path DIR) [options]
#
# Source (exactly one):
#   --pr N           fetch refs pull/N/head from --remote into a detached worktree
#                    ROOT/checkouts/pr-N
#   --branch B       fetch refs/heads/B from --remote into a detached worktree
#                    ROOT/checkouts/branch-<B with "/" replaced by "-">
#   --path DIR       use DIR as is (must hold app.json and gateway-patches/apply.sh);
#                    nothing is written to git; DIRTY=1 is reported when it has
#                    uncommitted changes
#
# Options:
#   --root DIR       required; the root verify-init.sh created (needs ROOT/verify.env)
#   --repo DIR       git repository to fetch into and add worktrees to (default: the
#                    git toplevel of the directory holding this script)
#   --remote NAME    git remote to fetch from (default: origin)
#   --sets LIST      comma list of patch sets, e.g. b,k (default: all, no --only)
#   --no-restart     patch and reinstall but leave the gateway stopped
#   --dry-run        fetch and resolve the commit (this only writes FETCH_HEAD in
#                    --repo), then print what a real run would do; creates nothing
#   -h, --help       show this help
#
# Safety: nothing is written outside --root/checkouts in this step. Branches of
# --repo are never created, moved or deleted, and other worktrees are never
# touched. A checkout whose working tree has changes is refused, never reset, and
# a checkouts entry that is not a worktree of --repo is never deleted.
# Errors: a line starting with "!! " on stderr and a non-zero exit (2 = usage).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_verify_common.sh
source "$SCRIPT_DIR/_verify_common.sh"

# A stray GIT_DIR from the caller would redirect every git call below.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR
export GIT_TERMINAL_PROMPT=0

usage() {
  sed -n '2,/^$/{/^$/d;s/^# \{0,1\}//;p}' "${BASH_SOURCE[0]}"
}

ROOT_ARG=""
REPO_ARG=""
REMOTE="origin"
PR=""
BRANCH=""
SRC_PATH=""
SETS=""
SETS_GIVEN=0
KIND=""
NO_RESTART=0
DRY_RUN=0
NSRC=0

need_value() { [ "$2" -ge 2 ] || vusage_die "option $1 needs a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root) need_value "$1" $#; ROOT_ARG="$2"; shift 2 ;;
    --repo) need_value "$1" $#; REPO_ARG="$2"; shift 2 ;;
    --remote) need_value "$1" $#; REMOTE="$2"; shift 2 ;;
    --pr) need_value "$1" $#; KIND=pr; PR="$2"; NSRC=$((NSRC + 1)); shift 2 ;;
    --branch) need_value "$1" $#; KIND=branch; BRANCH="$2"; NSRC=$((NSRC + 1)); shift 2 ;;
    --path) need_value "$1" $#; KIND=path; SRC_PATH="$2"; NSRC=$((NSRC + 1)); shift 2 ;;
    --sets) need_value "$1" $#; SETS="$2"; SETS_GIVEN=1; shift 2 ;;
    --no-restart) NO_RESTART=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) vusage_die "unknown option: $1" ;;
  esac
done
export DRY_RUN

# ---- argument validation (usage errors exit 2) -------------------------------
[ -n "$ROOT_ARG" ] || vusage_die "--root is required"
[ "$NSRC" -ge 1 ] || vusage_die "give exactly one of --pr, --branch, --path"
[ "$NSRC" -le 1 ] || vusage_die "give exactly one of --pr, --branch, --path (got $NSRC)"

if [ "$KIND" = pr ]; then
  [[ "$PR" =~ ^[1-9][0-9]*$ ]] || vusage_die "invalid --pr '$PR' (use a positive integer)"
elif [ "$KIND" = branch ]; then
  case "$BRANCH" in
    '' | -* | *'@{'*) vusage_die "invalid --branch '$BRANCH'" ;;
  esac
  git check-ref-format --branch "$BRANCH" >/dev/null 2>&1 \
    || vusage_die "invalid --branch '$BRANCH' (not a valid branch name)"
else
  [ -n "$SRC_PATH" ] || vusage_die "--path must not be empty"
fi

case "$REMOTE" in '' | -*) vusage_die "invalid --remote '$REMOTE'" ;; esac
if [ "$SETS_GIVEN" = 1 ]; then
  [[ "$SETS" =~ ^[a-z0-9]+(,[a-z0-9]+)*$ ]] \
    || vusage_die "invalid --sets '$SETS' (use a comma list such as b,k)"
fi

ROOT=$(vsafe_root "$ROOT_ARG") || exit $?
ROOT_RESOLVED="$ROOT"
[ -f "$ROOT/verify.env" ] \
  || vdie "$ROOT/verify.env not found: run scripts/verify-init.sh --root $ROOT first" 2
vread_env "$ROOT/verify.env"
[ "$ROOT" = "$ROOT_RESOLVED" ] \
  || vdie "$ROOT_RESOLVED/verify.env belongs to another root ($ROOT); was the directory moved?"

command -v git >/dev/null 2>&1 || vdie "git is not on PATH"

# A checkout must hold the app and the patch scripts.
check_tree_files() {
  [ -f "$1/app.json" ] && [ -f "$1/gateway-patches/apply.sh" ] \
    || vdie "$1 lacks app.json or gateway-patches/apply.sh: not a slack-channels-onboard tree"
}

# ---- source ------------------------------------------------------------------
SHA=""
DIRTY=0
CHECKOUT=""
ID=""

if [ "$KIND" = path ]; then
  [ -d "$SRC_PATH" ] || vusage_die "--path is not a directory: $SRC_PATH"
  CHECKOUT=$(realpath -- "$SRC_PATH")
  ID="$CHECKOUT"
  check_tree_files "$CHECKOUT"
  if [ "$(git -C "$CHECKOUT" rev-parse --is-inside-work-tree 2>/dev/null || true)" = true ]; then
    SHA=$(git -C "$CHECKOUT" rev-parse HEAD 2>/dev/null) || SHA="unknown"
    if [ -n "$(git -C "$CHECKOUT" status --porcelain -- . 2>/dev/null)" ]; then DIRTY=1; fi
  else
    SHA="unknown"
  fi
else
  # The default repo is the toplevel of the directory holding this script. When
  # the script is run from one of ROOT/checkouts (a worktree) that is that
  # worktree. It works all the same: worktrees share the object store, and
  # `git worktree add` can be run from any of them.
  if [ -n "$REPO_ARG" ]; then
    [ -d "$REPO_ARG" ] || vusage_die "--repo is not a directory: $REPO_ARG"
    REPO=$(realpath -- "$REPO_ARG")
  else
    REPO=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null) \
      || vdie "cannot find the git repository of $SCRIPT_DIR; pass --repo"
  fi
  REPO_COMMON=$(cd -- "$REPO" && realpath -- "$(git rev-parse --git-common-dir 2>/dev/null)") \
    || vdie "$REPO is not a git repository"

  if [ "$KIND" = pr ]; then
    ID="$PR"
    REFSPEC="pull/$PR/head"
    DIR="$ROOT/checkouts/pr-$PR"
  else
    ID="$BRANCH"
    REFSPEC="refs/heads/$BRANCH"
    DIR="$ROOT/checkouts/branch-${BRANCH//\//-}"
  fi
  CHECKOUT="$DIR"

  vlog "fetch: $REMOTE $REFSPEC into $REPO"
  # Resolve FETCH_HEAD right after the fetch; no other fetch may run in between.
  SHA=$(git -C "$REPO" fetch --no-tags -q -- "$REMOTE" "$REFSPEC" && git -C "$REPO" rev-parse FETCH_HEAD) \
    || vdie "git fetch of $REFSPEC from $REMOTE failed (in $REPO)"
  [[ "$SHA" =~ ^[0-9a-f]{40,64}$ ]] || vdie "unexpected FETCH_HEAD value: $SHA"
  # Checked on the fetched commit so that a bad one never gets a checkout.
  for f in app.json gateway-patches/apply.sh; do
    git -C "$REPO" cat-file -e "$SHA:$f" 2>/dev/null \
      || vdie "$REMOTE $REFSPEC ($SHA) lacks $f: not a slack-channels-onboard tree"
  done

  if [ -e "$DIR" ] || [ -L "$DIR" ]; then
    top=$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null || true)
    common=$(cd -- "$DIR" 2>/dev/null && realpath -- "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null || true)
    if [ -z "$top" ] || [ "$(realpath -- "$top")" != "$(realpath -- "$DIR")" ] || [ "$common" != "$REPO_COMMON" ]; then
      vdie "$DIR exists but is not a git worktree of $REPO; move it away yourself (nothing is deleted)"
    fi
    if [ -n "$(git -C "$DIR" status --porcelain)" ]; then
      vdie "$DIR has uncommitted changes; commit or discard them yourself (nothing is reset)"
    fi
    vrun git -C "$DIR" checkout -q --detach --force "$SHA" -- \
      || vdie "git checkout of $SHA in $DIR failed"
  else
    vrun mkdir -p -- "$ROOT/checkouts"
    vrun git -C "$REPO" worktree add -q --detach "$DIR" "$SHA" \
      || vdie "git worktree add of $SHA at $DIR failed (a stale registration? try: git -C $REPO worktree prune)"
  fi
  if [ "$DRY_RUN" = 0 ]; then
    check_tree_files "$DIR"
    [ "$(git -C "$DIR" rev-parse HEAD)" = "$SHA" ] || vdie "$DIR is not at $SHA after checkout"
  fi
fi

vlog "source: $KIND $ID at ${SHA:0:12} ($CHECKOUT)"
if [ "$DIRTY" = 1 ]; then
  vwarn "DIRTY=1: $CHECKOUT has uncommitted changes; they are installed as they are"
fi

# ---- plan (dry run) / not implemented yet ------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  plan() { printf '[dry-run] %s\n' "$*"; }
  APPLY="env KC_SITE_OVERRIDE=$KC_SITE KC_PYTHON=$VENV/bin/python bash $CHECKOUT/gateway-patches/apply.sh${SETS:+ --only $SETS}"
  vlog "plan (nothing was created; later steps are not implemented yet)"
  plan "1. stop: systemctl --user stop $UNIT"
  plan "2. reset kiro_crew: replace $KC_SITE with a copy of $KC_SRC/src/kiro_crew"
  plan "3. apply.sh (first run): $APPLY"
  plan "4. apply.sh (rerun): $APPLY"
  plan "5. reinstall app: slack-channels-onboard from $CHECKOUT into $KIROCREW_HOME (gateway stopped)"
  if [ "$NO_RESTART" = 1 ]; then
    plan "6. start: skipped (--no-restart)"
    plan "7. health check: skipped (--no-restart)"
    plan "8. journal scan: skipped (--no-restart)"
  else
    plan "6. start: systemctl --user start $UNIT"
    plan "7. health check: wait for http://127.0.0.1:$PORT"
    plan "8. journal scan: journalctl --user -u $UNIT for slack-channels-onboard errors"
  fi
  plan "9. write state: a record of this run under $ROOT/state"
  exit 0
fi

vdie "not implemented yet: reset + apply (Task 5)"
