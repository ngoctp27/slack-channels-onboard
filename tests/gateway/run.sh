#!/usr/bin/env bash
# Run tests/gateway on a real Kiro Crew package patched by gateway-patches/apply.sh.
#
# The behaviour tests import kiro_crew, so they need the actual gateway code with
# the patch sets applied. This script builds that in a throwaway directory and
# never touches the checkout it copies from or your own Kiro Crew install.
#
# Environment:
#   KC_REF                  Kiro Crew tag to clone when KC_SRC is unset (default v0.10.0)
#   KC_SRC                  an existing Kiro Crew source tree; it is copied, never edited in place
#   KC_PYTHON               interpreter used to create the venv, must be >= 3.12 (default python3)
#   KC_UPSTREAM_REGRESSION  non-empty: also run Kiro Crew's own test suite before and after
#                           patching and print which tests newly fail / newly pass
#   KC_UPSTREAM_TESTS       what that run executes, relative to the Kiro Crew tree (default: the
#                           test files that mention kiro_crew.slack; "test" runs the whole suite)
#   KC_KEEP=1               keep the work directory (printed at the end)
#
# The exit status is the result of `pytest tests/gateway` only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KC_REF="${KC_REF:-v0.10.0}"
KC_SRC="${KC_SRC:-}"
KC_PYTHON="${KC_PYTHON:-python3}"
KC_UPSTREAM_REGRESSION="${KC_UPSTREAM_REGRESSION:-}"
KC_KEEP="${KC_KEEP:-}"

if ! "$KC_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
  echo "!! KC_PYTHON ($KC_PYTHON) must be Python 3.12 or newer (Kiro Crew requires it)" >&2
  exit 2
fi

WORK="$(mktemp -d)"
cleanup() {
  local rc=$?
  if [ "$KC_KEEP" = "1" ]; then
    echo "kept work directory: $WORK"
  else
    rm -rf "$WORK"
  fi
  exit "$rc"
}
trap cleanup EXIT

if [ -n "$KC_SRC" ]; then
  [ -d "$KC_SRC/src/kiro_crew" ] || { echo "!! KC_SRC has no src/kiro_crew: $KC_SRC" >&2; exit 2; }
  cp -r "$KC_SRC" "$WORK/kirocrew"
  chmod -R u+w "$WORK/kirocrew"
else
  git clone -q -c advice.detachedHead=false --depth 1 --branch "$KC_REF" https://github.com/kirodotdev/KiroCrew.git "$WORK/kirocrew"
fi

# The patch scripts look for the pipx venv under $HOME; give them one in $WORK.
export HOME="$WORK/home"
mkdir -p "$HOME"
VENV="$HOME/.local/share/pipx/venvs/kirocrew"
"$KC_PYTHON" -m venv "$VENV"
PY="$VENV/bin/python"
"$PY" -m pip install -q --disable-pip-version-check -e "$WORK/kirocrew[dev]"

# Failed/errored node ids of Kiro Crew's own suite, one per line, sorted.
run_upstream() {
  local out="$1" log="$1.log"
  local targets
  if [ -n "${KC_UPSTREAM_TESTS:-}" ]; then
    targets="$KC_UPSTREAM_TESTS"
  else
    targets="$(cd "$WORK/kirocrew" && grep -rl --include='test_*.py' 'kiro_crew\.slack' test | LC_ALL=C sort | tr '\n' ' ')"
  fi
  # shellcheck disable=SC2086
  (cd "$WORK/kirocrew" && "$PY" -m pytest $targets -q -p no:cacheprovider -n auto -rfE --color=no >"$log" 2>&1) || true
  grep -E '^(FAILED|ERROR) [^ ]+\.py' "$log" | sed -E 's/^(FAILED|ERROR) ([^ ]+).*/\1 \2/' | LC_ALL=C sort -u >"$out" || true
}

if [ -n "$KC_UPSTREAM_REGRESSION" ]; then
  echo ">>> upstream suite on the pristine tree"
  run_upstream "$WORK/upstream-pristine.txt"
fi

echo ">>> applying gateway-patches"
KC_SITE_OVERRIDE="$WORK/kirocrew/src/kiro_crew" bash "$ROOT/gateway-patches/apply.sh" >"$WORK/apply.log" 2>&1 || true
if ! grep -q "All sets applied" "$WORK/apply.log" || grep -qE "CHECK ANCHORS|^!!" "$WORK/apply.log"; then
  cat "$WORK/apply.log" >&2
  echo "!! apply.sh did not apply every set" >&2
  exit 1
fi

if [ -n "$KC_UPSTREAM_REGRESSION" ]; then
  echo ">>> upstream suite on the patched tree"
  run_upstream "$WORK/upstream-patched.txt"
  echo "newly failing:"
  LC_ALL=C comm -13 "$WORK/upstream-pristine.txt" "$WORK/upstream-patched.txt" | sed 's/^/  /'
  echo "newly passing:"
  LC_ALL=C comm -23 "$WORK/upstream-pristine.txt" "$WORK/upstream-patched.txt" | sed 's/^/  /'
fi

echo ">>> pytest tests/gateway"
cd "$ROOT"
"$PY" -m pytest tests/gateway -q -p no:cacheprovider
