#!/usr/bin/env bash
# verify-init.sh - one-time setup of a separate Kiro Crew "verify" gateway.
#
# The verify gateway has its own venv and its own KIROCREW_HOME under --root and
# runs as a systemd user unit, so a feature branch of this app can be tried on it
# (see verify-install.sh) without touching the real gateway, ~/.kiro/crew or the
# default pipx venv. HOME is never changed. No sudo is ever run.
#
# Usage:
#   scripts/verify-init.sh --root DIR [options]
#
# Options:
#   --root DIR             required; everything is created under it
#   --kc-ref REF           Kiro Crew tag or branch to clone (default: v0.10.0)
#   --port N               gateway port, 1024..65535 (default: 8790)
#   --name NAME            instance name, [a-z0-9][a-z0-9-]{0,30} (default: verify)
#   --python PY            Python >= 3.12 (default: first of python3.12, python3)
#   --admin-env-file FILE  file with KIROCREW_ADMIN_USER_IDS=..., used by the unit
#                          as EnvironmentFile; stored as an absolute path, never read
#   --skip-slack           do not run the Slack setup
#   --enable-linger        also run `loginctl enable-linger` so the unit survives logout
#   --dry-run              run the preflight, print the plan, create nothing
#   -h, --help             show this help
#
# Environment:
#   SYSTEMD_USER_DIR       where the unit file goes (default: $HOME/.config/systemd/user)
#   KC_REPO_URL            Kiro Crew git URL (default: https://github.com/kirodotdev/KiroCrew.git)
#
# Writes only inside --root, plus
#   ${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}/kirocrew-verify-<name>.service
# Errors: a line starting with "!! " on stderr and a non-zero exit (2 = usage).

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_verify_common.sh
source "$SCRIPT_DIR/_verify_common.sh"

usage() {
  sed -n '2,/^$/{/^$/d;s/^# \{0,1\}//;p}' "${BASH_SOURCE[0]}"
}

ROOT_ARG=""
KC_REF="v0.10.0"
PORT="8790"
NAME="verify"
PYTHON_ARG=""
ADMIN_ENV_ARG=""
SKIP_SLACK=0
ENABLE_LINGER=0
DRY_RUN=0
KC_REPO_URL="${KC_REPO_URL:-https://github.com/kirodotdev/KiroCrew.git}"

need_value() { [ "$2" -ge 2 ] || vusage_die "option $1 needs a value"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --root) need_value "$1" $#; ROOT_ARG="$2"; shift 2 ;;
    --kc-ref) need_value "$1" $#; KC_REF="$2"; shift 2 ;;
    --port) need_value "$1" $#; PORT="$2"; shift 2 ;;
    --name) need_value "$1" $#; NAME="$2"; shift 2 ;;
    --python) need_value "$1" $#; PYTHON_ARG="$2"; shift 2 ;;
    --admin-env-file) need_value "$1" $#; ADMIN_ENV_ARG="$2"; shift 2 ;;
    --skip-slack) SKIP_SLACK=1; shift ;;
    --enable-linger) ENABLE_LINGER=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h | --help) usage; exit 0 ;;
    *) vusage_die "unknown option: $1" ;;
  esac
done
export DRY_RUN

# ---- argument validation (usage errors exit 2) -------------------------------
[ -n "$ROOT_ARG" ] || vusage_die "--root is required"
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]{0,30}$ ]] || vusage_die "invalid --name '$NAME' (use [a-z0-9][a-z0-9-]{0,30})"
[[ "$PORT" =~ ^[0-9]{1,5}$ ]] && [ "$((10#$PORT))" -ge 1024 ] && [ "$((10#$PORT))" -le 65535 ] \
  || vusage_die "invalid --port '$PORT' (use an integer 1024..65535)"
PORT=$((10#$PORT))
[ -n "$KC_REF" ] || vusage_die "--kc-ref must not be empty"
case "$KC_REF" in -*) vusage_die "invalid --kc-ref '$KC_REF'" ;; esac

ROOT=$(vsafe_root "$ROOT_ARG") || exit $?

ADMIN_ENV_FILE=""
if [ -n "$ADMIN_ENV_ARG" ]; then
  [ -f "$ADMIN_ENV_ARG" ] || vusage_die "--admin-env-file is not a regular file: $ADMIN_ENV_ARG"
  ADMIN_ENV_FILE=$(realpath -- "$ADMIN_ENV_ARG")
fi

UNIT="kirocrew-verify-$NAME.service"
UNIT_FILE="${SYSTEMD_USER_DIR:-$HOME/.config/systemd/user}/$UNIT"
KC_SRC="$ROOT/kc-src"
VENV="$ROOT/venv"
KIROCREW_HOME="$ROOT/home"

# ---- preflight ---------------------------------------------------------------
vlog "preflight"

PY=""
if [ -n "$PYTHON_ARG" ]; then
  vpy_ok "$PYTHON_ARG" || vdie "--python '$PYTHON_ARG' is not a Python >= 3.12"
  PY="$PYTHON_ARG"
else
  for cand in python3.12 python3; do
    if vpy_ok "$cand"; then PY="$cand"; break; fi
  done
  [ -n "$PY" ] || vdie "no Python >= 3.12 found (tried python3.12, python3); pass --python"
fi

command -v git >/dev/null 2>&1 || vdie "git is not on PATH"

if ! systemctl --user show-environment >/dev/null 2>&1; then
  if [ "$DRY_RUN" = 1 ]; then
    vwarn "systemctl --user is not usable here; a real run would stop"
  else
    vdie "systemctl --user is not usable (no user systemd session?)"
  fi
fi

if ! command -v bwrap >/dev/null 2>&1; then
  vwarn "bwrap not found: workspace confinement (Set T) will not work. Install it: sudo apt install bubblewrap"
fi

if ! "$PY" -c 'import socket, sys
s = socket.socket()
try:
    s.bind(("127.0.0.1", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()' "$PORT" 2>/dev/null; then
  if systemctl --user is-active --quiet "$UNIT" 2>/dev/null; then
    vlog "port $PORT is held by the active unit $UNIT (re-run); continuing"
  else
    vdie "port $PORT on 127.0.0.1 is already in use; pick another with --port"
  fi
fi

# ---- plan --------------------------------------------------------------------
if [ "$DRY_RUN" = 1 ]; then
  plan() { printf '[dry-run] %s\n' "$*"; }
  vlog "plan (nothing is created)"
  plan "1. clone: $KC_REPO_URL at $KC_REF into $KC_SRC"
  plan "2. venv+pip install: $PY -m venv $VENV, then pip install $KC_SRC"
  plan "3. config set: KIROCREW_HOME=$KIROCREW_HOME, gateway port $PORT, agent.apps_allow_third_party true"
  if [ "$SKIP_SLACK" = 1 ]; then
    plan "4. slack setup: skipped (--skip-slack)"
  else
    plan "4. slack setup: kirocrew slack setup (interactive; needs Slack tokens)"
  fi
  plan "5. write unit: $UNIT_FILE${ADMIN_ENV_FILE:+ (EnvironmentFile=$ADMIN_ENV_FILE)}"
  plan "6. daemon-reload: systemctl --user daemon-reload"
  plan "7. enable: systemctl --user enable $UNIT"
  if [ "$ENABLE_LINGER" = 1 ]; then
    plan "8. linger: loginctl enable-linger"
    plan "9. write verify.env: $ROOT/verify.env"
  else
    plan "8. write verify.env: $ROOT/verify.env"
  fi
  exit 0
fi

vdie "not implemented yet"
