#!/usr/bin/env bash
# verify-install.sh - put a feature branch or PR of this app on the separate Kiro
# Crew "verify" gateway that verify-init.sh set up.
#
# Repeatable: every run takes the source, checks it out under --root, resets the
# verify gateway's kiro_crew package, applies the gateway patches, reinstalls
# the app, starts the gateway, waits for /api/health, scans the journal for
# errors of the app and records the run in ROOT/state/current.json.
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
#   --no-restart     patch and reinstall the app, but leave the gateway stopped (no
#                    start, health check or journal scan); state is written with
#                    "started": false
#   --dry-run        fetch and resolve the commit (this only writes FETCH_HEAD in
#                    --repo), then print what a real run would do; creates nothing
#   -h, --help       show this help
#
# Environment (whole seconds unless noted):
#   VERIFY_HEALTH_TIMEOUT   how long to wait for /api/health after the start
#                           (default 60)
#   VERIFY_SETTLE_SECS      wait between the first healthy answer and the journal
#                           scan, so late start-up errors show up (default 5)
#   VERIFY_HEALTH_INTERVAL  seconds between two health polls, may be fractional
#                           (default 2; the tests use 0.2)
#
# Steps of a real run: stop the unit, reset kiro_crew, apply.sh twice, reinstall
# the app while the unit is stopped (`kirocrew app uninstall` when it is already
# installed, then `install` and `enable`; with the gateway stopped Kiro Crew
# works on the files of KIROCREW_HOME), start the unit, poll
# http://127.0.0.1:PORT/api/health, scan `journalctl --user -u UNIT --since
# <time of the start>` and write the state file. The scan fails the run on a
# "Traceback" line, or a line naming slack-channels-onboard or
# slack_channels_onboard together with error, exception or failed (the app name
# and those words are matched without regard to case); at most 40 of the matching
# lines are printed. A health timeout or a journal problem leaves the gateway
# running so it can be inspected; the message says so and names the log command.
# ROOT/state/current.json is written only by a run that got through every step
# (source, id, sha, dirty, sets "all" or a list, checkout, applied_at in UTC,
# unit, port, apply_log, started). `kirocrew token` is never run and the .env of
# the verify gateway is never read: the summary prints the command only.
#
# Safety: writes only under --root (checkouts, logs, the venv's kiro_crew
# package). Branches of --repo are never created, moved or deleted, and other
# worktrees are never touched. A checkout whose working tree has changes is
# refused, never reset, and a checkouts entry that is not a worktree of --repo is
# never deleted. The kiro_crew reset deletes KC_SITE only when it is a real
# directory path strictly inside the venv (basename kiro_crew, under a
# site-packages component) and the pristine copy is there to replace it; the new
# copy is made next to it first, so a failed copy keeps the old package.
# apply.sh output goes to ROOT/logs/apply-<UTC timestamp>.log (one header per
# run); a run fails on a non-zero exit, a missing "All sets applied", or a
# "CHECK ANCHORS", "!!" or "FAILED" line, and the gateway stays stopped.
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

HEALTH_TIMEOUT="${VERIFY_HEALTH_TIMEOUT:-60}"
SETTLE_SECS="${VERIFY_SETTLE_SECS:-5}"
HEALTH_INTERVAL="${VERIFY_HEALTH_INTERVAL:-2}"
[[ "$HEALTH_TIMEOUT" =~ ^[0-9]+$ ]] \
  || vusage_die "invalid VERIFY_HEALTH_TIMEOUT '$HEALTH_TIMEOUT' (use whole seconds)"
[[ "$SETTLE_SECS" =~ ^[0-9]+$ ]] \
  || vusage_die "invalid VERIFY_SETTLE_SECS '$SETTLE_SECS' (use whole seconds)"
[[ "$HEALTH_INTERVAL" =~ ^([0-9]+\.?[0-9]*|\.[0-9]+)$ ]] && [[ "$HEALTH_INTERVAL" =~ [1-9] ]] \
  || vusage_die "invalid VERIFY_HEALTH_INTERVAL '$HEALTH_INTERVAL' (use seconds above 0, e.g. 2 or 0.5)"

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

# ---- plan (dry run) ----------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  plan() { printf '[dry-run] %s\n' "$*"; }
  APPLY="env KC_SITE_OVERRIDE=$KC_SITE KC_PYTHON=$VENV/bin/python bash $CHECKOUT/gateway-patches/apply.sh${SETS:+ --only $SETS}"
  vlog "plan (nothing was created)"
  plan "1. stop: systemctl --user stop $UNIT"
  plan "2. reset kiro_crew: replace $KC_SITE with a copy of $KC_SRC/src/kiro_crew"
  plan "3. apply.sh (first run): $APPLY"
  plan "4. apply.sh (rerun): $APPLY"
  plan "5. reinstall app: kirocrew app uninstall (when installed), install $CHECKOUT, enable slack-channels-onboard in $KIROCREW_HOME (gateway stopped)"
  if [ "$NO_RESTART" = 1 ]; then
    plan "6. start: skipped (--no-restart)"
    plan "7. health check: skipped (--no-restart)"
    plan "8. journal scan: skipped (--no-restart)"
  else
    plan "6. start: systemctl --user start $UNIT"
    plan "7. health check: wait up to ${HEALTH_TIMEOUT}s for http://127.0.0.1:$PORT/api/health"
    plan "8. journal scan: journalctl --user -u $UNIT for slack-channels-onboard errors"
  fi
  plan "9. write state: $ROOT/state/current.json, then print the summary"
  exit 0
fi

# ---- check the reset target before touching anything ---------------------------
# The reset is the only place the script deletes anything outside its own
# checkouts, so every condition that makes the rm safe is checked first, before
# the gateway is stopped.
[ -f "$KC_SRC/src/kiro_crew/__init__.py" ] \
  || vdie "$KC_SRC/src/kiro_crew/__init__.py not found: the pristine Kiro Crew copy is missing; run scripts/verify-init.sh --root $ROOT"
[ -n "$VENV" ] && [ -n "$KC_SITE" ] || vdie "VENV or KC_SITE is empty in $ROOT/verify.env"
[ ! -L "$KC_SITE" ] || vdie "refusing to reset $KC_SITE: it is a symlink"
VENV_REAL=$(realpath -- "$VENV") || vdie "cannot resolve VENV: $VENV"
SITE_REAL=$(realpath -m -- "$KC_SITE") || vdie "cannot resolve KC_SITE: $KC_SITE"
SRC_PKG_REAL=$(realpath -- "$KC_SRC/src/kiro_crew") || vdie "cannot resolve $KC_SRC/src/kiro_crew"
ROOT_REAL=$(realpath -- "$ROOT") || vdie "cannot resolve ROOT: $ROOT"
case "$VENV_REAL" in
  "$ROOT_REAL"/*) ;;
  *) vdie "refusing to reset: the venv $VENV_REAL is not inside $ROOT_REAL" ;;
esac
case "$SITE_REAL" in
  "$VENV_REAL"/*) ;;
  *) vdie "refusing to reset $KC_SITE: it is not strictly inside the venv $VENV_REAL" ;;
esac
[ "$(basename -- "$SITE_REAL")" = kiro_crew ] \
  || vdie "refusing to reset $SITE_REAL: its name is not kiro_crew"
case "/${SITE_REAL#"$VENV_REAL"/}/" in
  */site-packages/*) ;;
  *) vdie "refusing to reset $SITE_REAL: no site-packages directory in its path" ;;
esac
[ "$SITE_REAL" != "$SRC_PKG_REAL" ] || vdie "refusing to reset $SITE_REAL: it is the pristine copy"

# ---- stop the gateway --------------------------------------------------------
command -v systemctl >/dev/null 2>&1 || vdie "systemctl is not on PATH"
vlog "stop: systemctl --user stop $UNIT"
set +e
stop_out=$(systemctl --user stop "$UNIT" 2>&1)
stop_rc=$?
set -e
if [ "$stop_rc" = 5 ]; then
  # Some systemd versions answer an unknown or not-loaded unit with exit 5.
  vwarn "$UNIT is not loaded (systemctl exit 5); nothing to stop"
elif [ "$stop_rc" != 0 ]; then
  vdie "systemctl --user stop $UNIT failed (exit $stop_rc): $stop_out"
fi

# ---- reset kiro_crew to the pristine copy -------------------------------------
vlog "reset: $SITE_REAL <- $KC_SRC/src/kiro_crew"
NEW_SITE="$SITE_REAL.verify-new.$$"
mkdir -p -- "$(dirname -- "$SITE_REAL")" \
  || vdie "cannot create $(dirname -- "$SITE_REAL")"
[ ! -e "$NEW_SITE" ] && [ ! -L "$NEW_SITE" ] || vdie "$NEW_SITE already exists"
reset_fail() {
  rm -rf -- "$NEW_SITE"
  vdie "$1"
}
cp -r -- "$SRC_PKG_REAL" "$NEW_SITE" || reset_fail "copying $SRC_PKG_REAL failed; $SITE_REAL is unchanged"
chmod -R u+w -- "$NEW_SITE" || reset_fail "chmod of the new copy failed; $SITE_REAL is unchanged"
rm -rf -- "$SITE_REAL" \
  || vdie "cannot remove the old $SITE_REAL; it may be partly deleted. The complete copy is kept in $NEW_SITE: replace $SITE_REAL with it by hand, or run verify-init.sh again"
mv -- "$NEW_SITE" "$SITE_REAL" \
  || vdie "cannot move the new copy to $SITE_REAL; the venv has no kiro_crew now. The complete copy is kept in $NEW_SITE: move it to $SITE_REAL by hand, or run verify-init.sh again"

# ---- apply the gateway patches (twice: the second run must be a no-op) --------
LOG="$ROOT/logs/apply-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p -- "$ROOT/logs" || vdie "cannot create $ROOT/logs"
ONLY=()
if [ -n "$SETS" ]; then ONLY=(--only "$SETS"); fi

run_apply() {
  local run="$1" out rc cmd why=""
  cmd="env KC_SITE_OVERRIDE=$KC_SITE KC_PYTHON=$VENV/bin/python bash $CHECKOUT/gateway-patches/apply.sh${SETS:+ --only $SETS}"
  vlog "apply.sh, $run pass"
  set +e
  out=$(env KC_SITE_OVERRIDE="$KC_SITE" KC_PYTHON="$VENV/bin/python" \
    bash "$CHECKOUT/gateway-patches/apply.sh" ${ONLY[@]+"${ONLY[@]}"} 2>&1)
  rc=$?
  set -e
  printf '=== apply.sh %s run: %s ===\n%s\n' "$run" "$cmd" "$out" >>"$LOG" \
    || vdie "cannot write $LOG"

  [ "$rc" = 0 ] || why="exit status $rc"
  grep -q 'All sets applied' <<<"$out" || why="${why:+$why; }no 'All sets applied' line"
  ! grep -q 'CHECK ANCHORS' <<<"$out" || why="${why:+$why; }'CHECK ANCHORS' in the output"
  ! grep -q '^!!' <<<"$out" || why="${why:+$why; }a line starting with '!!'"
  ! grep -q 'FAILED' <<<"$out" || why="${why:+$why; }'FAILED' in the output"
  if [ -n "$why" ]; then
    printf -- '-- last 40 lines of the %s run (%s):\n' "$run" "$why" >&2
    tail -n 40 <<<"$out" >&2
    vdie "apply.sh failed on the $run run, full log: $LOG"
  fi
}

run_apply first
run_apply rerun
vlog "apply.sh: All sets applied on both runs, log: $LOG"

# ---- reinstall the app (the gateway is stopped) --------------------------------
# With the unit stopped `kirocrew app ...` falls back to the files of
# KIROCREW_HOME. A running unit would be asked over its dashboard instead, which
# is not what this step wants, so a running unit is refused.
if systemctl --user is-active --quiet "$UNIT" </dev/null 2>/dev/null; then
  vdie "$UNIT is active after the stop; refusing to reinstall the app into a running gateway"
fi

kc() { env KIROCREW_HOME="$KIROCREW_HOME" "$VENV/bin/kirocrew" "$@" </dev/null; }

kc_step() {
  local out rc
  set +e
  out=$(kc app "$@" 2>&1)
  rc=$?
  set -e
  if [ "$rc" != 0 ]; then
    printf -- '-- output of kirocrew app %s:\n' "$*" >&2
    tail -n 20 <<<"$out" >&2
    vdie "kirocrew app $1 failed (exit $rc); the gateway is stopped and kiro_crew is patched"
  fi
}

if [ -d "$KIROCREW_HOME/apps/slack-channels-onboard" ]; then
  vlog "app: uninstall slack-channels-onboard (data is kept)"
  kc_step uninstall slack-channels-onboard
fi
vlog "app: install $CHECKOUT"
kc_step install "$CHECKOUT"
vlog "app: enable slack-channels-onboard"
kc_step enable slack-channels-onboard

# ---- state and summary ------------------------------------------------------
write_state() {
  local started="$1"
  mkdir -p -- "$ROOT/state" || vdie "cannot create $ROOT/state"
  "$VENV/bin/python" - "$ROOT/state/current.json" "$KIND" "$ID" "$SHA" "$DIRTY" "$SETS" \
    "$CHECKOUT" "$UNIT" "$PORT" "$LOG" "$started" <<'PY' || vdie "cannot write $ROOT/state/current.json"
import datetime
import json
import os
import sys

path, kind, ident, sha, dirty, sets, checkout, unit, port, log, started = sys.argv[1:12]
state = {
    "source": kind,
    "id": ident,
    "sha": sha,
    "dirty": dirty == "1",
    "sets": sets.split(",") if sets else "all",
    "checkout": checkout,
    "applied_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "unit": unit,
    "port": int(port),
    "apply_log": log,
    "started": started == "1",
}
tmp = f"{path}.tmp.{os.getpid()}"
try:
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)
except BaseException:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
PY
}

print_summary() {
  vlog "sha: $SHA"
  vlog "sets: ${SETS:-all}"
  vlog "checkout: $CHECKOUT"
  vlog "log: $LOG"
  vlog "url: http://127.0.0.1:$PORT/"
  vlog "gateway log: journalctl --user -u $UNIT -f"
  vlog "dashboard token: $(printf 'KIROCREW_HOME=%q %q token' "$KIROCREW_HOME" "$VENV/bin/kirocrew")"
  if [ -n "$ADMIN_ENV_FILE" ]; then
    vlog "admins: KIROCREW_ADMIN_USER_IDS comes from the env file named in the unit: $ADMIN_ENV_FILE"
  else
    vlog "admins: none configured (no env file named in the unit)"
  fi
  vlog "state: $ROOT/state/current.json"
}

if [ "$NO_RESTART" = 1 ]; then
  write_state 0
  vlog "patched, gateway left stopped (--no-restart)"
  vlog "source: $KIND $ID at ${SHA:0:12}"
  print_summary
  exit 0
fi

# ---- start and check the gateway ----------------------------------------------
LOGCMD="journalctl --user -u $UNIT -f"
LEFT_RUNNING="the gateway is left running so you can look at it (log: $LOGCMD)"

START=$(date '+%Y-%m-%d %H:%M:%S')
vlog "start: systemctl --user start $UNIT"
set +e
start_out=$(systemctl --user start "$UNIT" 2>&1 </dev/null)
start_rc=$?
set -e
[ "$start_rc" = 0 ] \
  || vdie "systemctl --user start $UNIT failed (exit $start_rc): $start_out (log: $LOGCMD)"

HEALTH_URL="http://127.0.0.1:$PORT/api/health"
vlog "health: waiting up to ${HEALTH_TIMEOUT}s for $HEALTH_URL"
t0=$SECONDS
last_err=""
while true; do
  set +e
  last_err=$(curl -fsS -o /dev/null --max-time 3 "$HEALTH_URL" 2>&1 </dev/null)
  curl_rc=$?
  set -e
  [ "$curl_rc" != 0 ] || break
  if [ $((SECONDS - t0)) -ge "$HEALTH_TIMEOUT" ]; then
    printf -- '-- last 40 journal lines of %s:\n' "$UNIT" >&2
    journalctl --user -u "$UNIT" -n 40 --no-pager -o cat </dev/null >&2 || true
    vdie "no answer from $HEALTH_URL within ${HEALTH_TIMEOUT}s (last curl: ${last_err:-no output}); $LEFT_RUNNING"
  fi
  sleep "$HEALTH_INTERVAL"
done
vlog "health: ok"

[ "$SETTLE_SECS" = 0 ] || sleep "$SETTLE_SECS"

# ---- journal scan -------------------------------------------------------------
set +e
journal=$(journalctl --user -u "$UNIT" --since "$START" --no-pager -o cat </dev/null 2>&1)
journal_rc=$?
set -e
[ "$journal_rc" = 0 ] \
  || vdie "cannot read the journal of $UNIT (journalctl exit $journal_rc: $journal); $LEFT_RUNNING"

hits=()
while IFS= read -r line; do
  low="${line,,}"
  if [[ "$line" == *Traceback* ]]; then
    hits+=("$line")
  elif [[ "$low" == *slack-channels-onboard* || "$low" == *slack_channels_onboard* ]] \
    && [[ "$low" == *error* || "$low" == *exception* || "$low" == *failed* ]]; then
    hits+=("$line")
  fi
done <<<"$journal"

if [ "${#hits[@]}" -gt 0 ]; then
  shown=${#hits[@]}
  [ "$shown" -le 40 ] || shown=40
  printf -- '-- %d of %d journal lines that look like errors:\n' "$shown" "${#hits[@]}" >&2
  printf '%s\n' "${hits[@]:0:40}" >&2
  vdie "the journal of $UNIT has ${#hits[@]} error line(s) since the start; $LEFT_RUNNING"
fi
vlog "journal: no errors of slack-channels-onboard since the start"

write_state 1
vlog "gateway running and healthy"
print_summary
