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
#   KC_LAYOUT               where Kiro Crew is installed, the way the patch sets have to find it:
#                             pipx (default)  venv at the pipx path under a throwaway HOME;
#                                             apply.sh gets KC_SITE_OVERRIDE
#                             venv            venv outside the pipx path, reached through a
#                                             `kirocrew` link on PATH (like cloud-install.sh);
#                                             apply.sh gets no KC_SITE_OVERRIDE and no KC_PYTHON
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
KC_LAYOUT="${KC_LAYOUT:-pipx}"
case "$KC_LAYOUT" in pipx | venv) ;; *) echo "!! KC_LAYOUT must be pipx or venv, not: $KC_LAYOUT" >&2; exit 2 ;; esac

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

# A throwaway HOME either way, so the patch scripts never see the caller's own install.
export HOME="$WORK/home"
mkdir -p "$HOME"
if [ "$KC_LAYOUT" = pipx ]; then
  VENV="$HOME/.local/share/pipx/venvs/kirocrew"
else
  VENV="$WORK/venv"
fi
"$KC_PYTHON" -m venv "$VENV"
PY="$VENV/bin/python"
"$PY" -m pip install -q --disable-pip-version-check -e "$WORK/kirocrew[dev]"
if [ "$KC_LAYOUT" = venv ]; then
  [ -x "$VENV/bin/kirocrew" ] || { echo "!! the install did not create $VENV/bin/kirocrew" >&2; exit 1; }
  mkdir -p "$WORK/bin"
  ln -s "$VENV/bin/kirocrew" "$WORK/bin/kirocrew"
  export PATH="$WORK/bin:$PATH"
fi

# Set to 1 when either upstream run did not finish; the difference below is then unreliable.
UPSTREAM_INCOMPLETE=""

# Failed/errored node ids of Kiro Crew's own suite, one per line, sorted.
run_upstream() {
  local out="$1" log="$1.log"
  local targets
  if [ -n "${KC_UPSTREAM_TESTS:-}" ]; then
    targets="$KC_UPSTREAM_TESTS"
  else
    targets="$(cd "$WORK/kirocrew" && grep -rl --include='test_*.py' 'kiro_crew\.slack' test | LC_ALL=C sort | tr '\n' ' ')"
  fi
  # pytest exits 0 (all passed) or 1 (some failed). Anything else (2 interrupted or collection
  # error, 3 internal error, 4 usage, 5 no tests) means the run did not finish, and an empty
  # failure list would then look like "nothing changed".
  local rc=0
  # shellcheck disable=SC2086
  (cd "$WORK/kirocrew" && "$PY" -m pytest $targets -q -p no:cacheprovider -n auto -rfE --color=no >"$log" 2>&1) || rc=$?
  if [ "$rc" -gt 1 ]; then
    echo "!! upstream run did not complete (rc=$rc), see $log"
    UPSTREAM_INCOMPLETE=1
  fi
  echo "   pytest: $(grep -E '^[=]* *[0-9]+ (passed|failed|error|skipped)|no tests ran' "$log" | tail -n 1 || true)"
  # A parametrized id can contain spaces, so cut at the " - <message>" separator, not at the first space.
  { grep -E '^(FAILED|ERROR) [^ ]+\.py' "$log" || true; } | "$PY" -c '
import sys
for line in sys.stdin:
    kind, _, rest = line.rstrip("\n").partition(" ")
    print(kind, rest.partition(" - ")[0])
' | LC_ALL=C sort -u >"$out"
}

if [ -n "$KC_UPSTREAM_REGRESSION" ]; then
  echo ">>> upstream suite on the pristine tree"
  run_upstream "$WORK/upstream-pristine.txt"
fi

echo ">>> applying gateway-patches (layout: $KC_LAYOUT)"
if [ "$KC_LAYOUT" = pipx ]; then
  # KC_PYTHON here means "interpreter that builds the venv"; the sets read it as "gateway
  # interpreter", so it is never passed on.
  env -u KC_PYTHON KC_SITE_OVERRIDE="$WORK/kirocrew/src/kiro_crew" bash "$ROOT/gateway-patches/apply.sh" >"$WORK/apply.log" 2>&1 || true
else
  for _run in first rerun; do
    env -u KC_SITE_OVERRIDE -u KC_PYTHON bash "$ROOT/gateway-patches/apply.sh" >"$WORK/apply.log" 2>&1 || true
    if ! grep -q "All sets applied" "$WORK/apply.log" || grep -qE "CHECK ANCHORS|^!!" "$WORK/apply.log"; then
      echo "!! apply.sh failed on the $_run run" >&2
      break
    fi
  done
fi
if ! grep -q "All sets applied" "$WORK/apply.log" || grep -qE "CHECK ANCHORS|^!!" "$WORK/apply.log"; then
  cat "$WORK/apply.log" >&2
  echo "!! apply.sh did not apply every set" >&2
  exit 1
fi

if [ -n "$KC_UPSTREAM_REGRESSION" ]; then
  echo ">>> upstream suite on the patched tree"
  run_upstream "$WORK/upstream-patched.txt"
  unreliable=""
  [ -z "$UPSTREAM_INCOMPLETE" ] || unreliable=" (UNRELIABLE: an upstream run did not complete)"
  [ -z "$UPSTREAM_INCOMPLETE" ] || echo "!! the two lists below are unreliable, an upstream run did not complete"
  echo "newly failing:$unreliable"
  LC_ALL=C comm -13 "$WORK/upstream-pristine.txt" "$WORK/upstream-patched.txt" | sed 's/^/  /'
  echo "newly passing:$unreliable"
  LC_ALL=C comm -23 "$WORK/upstream-pristine.txt" "$WORK/upstream-patched.txt" | sed 's/^/  /'
fi

echo ">>> pytest tests/gateway"
cd "$ROOT"
"$PY" -m pytest tests/gateway -q -p no:cacheprovider
