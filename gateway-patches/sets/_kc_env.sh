# shellcheck shell=bash
# ============================================================================
# Shared by every repatch-set-*.sh: find the Python that runs the Kiro Crew
# gateway and the kiro_crew package directory to patch. Sourced, not run.
#
#   source "$(dirname "$0")/_kc_env.sh"; kc_env "Set X" || exit 1
#
# Sets, after a successful kc_env:
#   KC_PY  the interpreter: Python >= 3.12 that can import kiro_crew
#   SITE   the kiro_crew package directory the set edits
#   PYTHONPATH  prefixed with the parent of SITE, so a set's import checks load
#               the tree it just patched, not another install on the host
#
# Interpreter, first match wins:
#   1. KC_PYTHON, if set. A KC_PYTHON that does not work is an error; there is
#      no fallback, so the choice you made is never silently replaced.
#   2. The interpreter in the shebang of `kirocrew` on PATH. That covers a pipx
#      install and a plain venv (cloud-install.sh links ~/.local/bin/kirocrew
#      to <venv>/bin/kirocrew).
#   3. ~/.local/share/pipx/venvs/kirocrew/bin/python (pipx, kirocrew not on PATH).
# Package: KC_SITE_OVERRIDE if set, else the interpreter's kiro_crew directory.
#
# On failure it prints a line starting with "!!" and returns 1; the caller exits
# 1 so apply.sh stops instead of reporting sets it never applied.
# ============================================================================

_kc_env_works() { # <python> <pythonpath-prefix>
  # -B: the probe must not write __pycache__ into a tree a set may then refuse to patch.
  [ -n "$1" ] && [ -x "$1" ] || return 1
  PYTHONPATH="${2}${PYTHONPATH:+:$PYTHONPATH}" "$1" -B -c \
    'import sys; sys.exit(1) if sys.version_info < (3, 12) else None; import kiro_crew' >/dev/null 2>&1
}

_kc_env_shebang() { # print the interpreter named by the shebang of `kirocrew` on PATH
  local exe line prog arg
  exe=$(command -v kirocrew 2>/dev/null) || return 1
  IFS= read -r line <"$exe" || return 1
  case "$line" in "#!"*) ;; *) return 1 ;; esac
  read -r prog arg _ <<<"${line#\#!}"
  case "$prog" in
    */env) [ -n "$arg" ] && command -v "$arg" ;;
    *) printf '%s\n' "$prog" ;;
  esac
}

kc_env() { # <label, e.g. "Set N1">
  local label="${1:-patch}" pp="" cand
  if [ -n "${KC_SITE_OVERRIDE:-}" ]; then
    if [ ! -f "$KC_SITE_OVERRIDE/__init__.py" ]; then
      echo "!! $label: KC_SITE_OVERRIDE=$KC_SITE_OVERRIDE is not a kiro_crew package directory"
      return 1
    fi
    pp=$(cd "$KC_SITE_OVERRIDE/.." && pwd)
  fi

  KC_PY=""
  if [ -n "${KC_PYTHON:-}" ]; then
    if ! _kc_env_works "$KC_PYTHON" "$pp"; then
      echo "!! $label: KC_PYTHON=$KC_PYTHON is not a Python >= 3.12 that can import kiro_crew"
      return 1
    fi
    KC_PY=$KC_PYTHON
  else
    for cand in "$(_kc_env_shebang)" "$HOME/.local/share/pipx/venvs/kirocrew/bin/python"; do
      if _kc_env_works "$cand" "$pp"; then KC_PY=$cand; break; fi
    done
  fi
  if [ -z "$KC_PY" ]; then
    echo "!! $label: no Kiro Crew interpreter found (no kirocrew on PATH, no pipx venv);" \
      "set KC_PYTHON=/path/to/venv/bin/python"
    return 1
  fi

  if [ -n "${KC_SITE_OVERRIDE:-}" ]; then
    SITE=$KC_SITE_OVERRIDE
  else
    SITE=$("$KC_PY" -B -c 'import kiro_crew, os; print(os.path.dirname(kiro_crew.__file__))' 2>/dev/null)
    if [ -z "$SITE" ] || [ ! -f "$SITE/__init__.py" ]; then
      echo "!! $label: $KC_PY imports kiro_crew but its package directory was not found; set KC_SITE_OVERRIDE"
      return 1
    fi
    pp=$(cd "$SITE/.." && pwd)
  fi
  export PYTHONPATH="${pp}${PYTHONPATH:+:$PYTHONPATH}"
  return 0
}
