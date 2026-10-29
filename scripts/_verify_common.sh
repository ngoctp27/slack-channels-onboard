# shellcheck shell=bash
# Shared helpers for scripts/verify-init.sh and scripts/verify-install.sh.
# Sourced, never executed. It sets no shell options; the caller owns
# `set -euo pipefail`.
#
# Functions:
#   vlog MSG...        stdout ">>> MSG"
#   vwarn MSG...       stderr "-- warning: MSG"
#   vdie MSG [CODE]    stderr "!! MSG", exit CODE (default 1)
#   vusage_die MSG     stderr "!! MSG" + "see --help", exit 2
#   vpy_ok PY          status 0 iff PY runs and is Python >= 3.12
#   vsafe_root PATH    print the normalised absolute path, or exit 2 when it is
#                      empty, "/", $HOME, or at/under ~/.kiro/crew or the
#                      default pipx kirocrew venv
#   vrun CMD...        DRY_RUN=1: print "[dry-run] <quoted cmd>"; else run it
#   vread_env FILE     parse ROOT/verify.env WITHOUT sourcing it (VERIFY_FORMAT=1
#                      must be present)
#   vwrite_env FILE    write ROOT/verify.env atomically, mode 600
#
# verify.env keys (one KEY=VALUE per line, value taken verbatim, no quoting):
#   VERIFY_FORMAT (=1) ROOT NAME PORT KC_REF KC_SRC VENV KC_SITE
#   KIROCREW_HOME UNIT UNIT_FILE ADMIN_ENV_FILE (may be empty)

VERIFY_ENV_KEYS=(VERIFY_FORMAT ROOT NAME PORT KC_REF KC_SRC VENV KC_SITE
  KIROCREW_HOME UNIT UNIT_FILE ADMIN_ENV_FILE)

vlog() { printf '>>> %s\n' "$*"; }

vwarn() { printf -- '-- warning: %s\n' "$*" >&2; }

vdie() {
  printf '!! %s\n' "${1-}" >&2
  exit "${2:-1}"
}

vusage_die() {
  printf '!! %s\nsee --help\n' "${1-}" >&2
  exit 2
}

vpy_ok() {
  local py="${1-}"
  [ -n "$py" ] || return 1
  command -v -- "$py" >/dev/null 2>&1 || return 1
  "$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

vsafe_root() {
  local raw="${1-}" p home x
  [ -n "$raw" ] || vdie "root path must not be empty" 2
  [ -n "${HOME:-}" ] || vdie "HOME is not set" 2
  p=$(realpath -m -- "$raw") || vdie "cannot resolve root path: $raw" 2
  home=$(realpath -m -- "$HOME") || vdie "cannot resolve HOME" 2
  [ "$p" != "/" ] || vdie "refusing root '/'" 2
  [ "$p" != "$home" ] || vdie "refusing root equal to HOME: $p" 2
  for x in "$home/.kiro/crew" "$home/.local/share/pipx/venvs/kirocrew"; do
    case "$p" in
      "$x" | "$x"/*) vdie "refusing root $p: it is, or is inside, $x" 2 ;;
    esac
  done
  printf '%s\n' "$p"
}

vrun() {
  if [ "${DRY_RUN:-0}" = 1 ]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

_venv_key_ok() {
  local k
  for k in "${VERIFY_ENV_KEYS[@]}"; do
    [ "$k" = "$1" ] && return 0
  done
  return 1
}

vread_env() {
  local file="${1-}" line key val seen_format=0
  [ -f "$file" ] || vdie "env file not found: $file"
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in '' | '#'*) continue ;; esac
    [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]] || vdie "malformed line in $file: $line"
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    _venv_key_ok "$key" || vdie "unknown key '$key' in $file"
    if [ "$key" = VERIFY_FORMAT ]; then
      [ "$val" = 1 ] || vdie "unsupported VERIFY_FORMAT '$val' in $file"
      seen_format=1
    fi
    printf -v "$key" '%s' "$val"
  done <"$file"
  [ "$seen_format" = 1 ] || vdie "VERIFY_FORMAT is missing in $file"
}

vwrite_env() {
  local file="${1-}" tmp key val nl=$'\n'
  [ -n "$file" ] || vdie "vwrite_env needs a file"
  VERIFY_FORMAT="${VERIFY_FORMAT:-1}"
  for key in "${VERIFY_ENV_KEYS[@]}"; do
    val="${!key:-}"
    case "$val" in
      *"$nl"*) vdie "value of $key contains a newline" ;;
    esac
  done
  tmp=$(umask 077 && mktemp "$file.XXXXXX") || vdie "cannot create temp file next to $file"
  {
    for key in "${VERIFY_ENV_KEYS[@]}"; do
      printf '%s=%s\n' "$key" "${!key:-}"
    done
  } >"$tmp" || { rm -f -- "$tmp"; vdie "cannot write $tmp"; }
  chmod 600 -- "$tmp" && mv -f -- "$tmp" "$file" || { rm -f -- "$tmp"; vdie "cannot write $file"; }
}
