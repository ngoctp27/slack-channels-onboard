#!/usr/bin/env bash
# ============================================================================
# Set N1 — admins from KIROCREW_ADMIN_USER_IDS rank as owner on Slack, except
#          four actions that stay with the primary owner (2026-10-28).
#
# Kiro Crew 0.10.0 ONLY. Any other version stops with "CHECK ANCHORS" and writes
# nothing (the check runs before everything else, the idempotency check included).
#
# Before: the Slack gateway has exactly one owner (slack owner id). Everything the
# owner may do — approve cards, run owner commands — is unavailable to a second
# person unless they are a member (read-only).
# Now:
#   1. slack/handler_runtime/access.py: is_owner(user_id, *, primary=False). With
#      primary=False an id listed in the KIROCREW_ADMIN_USER_IDS environment
#      variable (comma separated, read on every call, same U/W rule as the owner)
#      also counts. primary=True matches the configured owner only. With no owner
#      configured nobody is an owner, admins included (fail closed). Admins are NOT
#      added to _allowed_users: the dashboard allowlist writers replace that set.
#   2. slack/transport.py: the two direct _allowed_users checks (authorize,
#      may_send_to) also accept an admin through _kc_admin_ok.
#   3. The four primary-owner-only actions refuse an admin with
#      "⛔ Chỉ owner chính dùng được lệnh này.":
#        - routing a message into a linked dashboard thread. An admin's message there
#          is dropped (the router returns True, so the turn does not fall through
#          into the dashboard session); a member keeps the Set O3 fall-through
#        - turning YOLO on / renewing it (/kirocrew yolo and !yolo; "off" stays open)
#        - minting a dashboard link (send_dashboard_link, one gate for /kirocrew
#          dashboard and !dashboard — this closes !dashboard for members too)
#        - linking a thread to the dashboard: !link-to-dashboard and the "Link to
#          Dashboard" button (slack/interactions.py), both end in the same import
#      The dashboard itself already compares against the primary owner id.
#
# An admin-opened thread in a sandboxed channel runs unsandboxed, like the owner's.
#
# Requires Set O3 (_kc_member_no_escalation_v1) and Set K. Idempotent via the
# _kc_multi_admin_v1 marker. Roll back: restore the *.bak-setn1-<stamp> files.
# ============================================================================
set -uo pipefail
SITE=${KC_SITE_OVERRIDE:-}; [ -n "$SITE" ] || SITE=$(python3 -c "import pathlib; g=list(pathlib.Path.home().joinpath('.local/share/pipx/venvs/kirocrew/lib').glob('python*/site-packages/kiro_crew')); print(g[0] if g else '')")
[ -n "$SITE" ] || { echo "Set N1: venv not found — skipping"; exit 0; }
FOUND=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SITE/__init__.py" 2>/dev/null | head -1)
grep -qx '__version__ = "0.10.0"' "$SITE/__init__.py" 2>/dev/null \
  || { echo "Set N1: Kiro Crew ${FOUND:-unknown} is not 0.10.0 — CHECK ANCHORS"; exit 1; }
VENV_PY=$(ls "$HOME"/.local/share/pipx/venvs/kirocrew/bin/python* 2>/dev/null | head -1 || true)
STAMP=$(date +%Y%m%d-%H%M%S)

"$VENV_PY" - "$SITE" "$STAMP" <<'PY'
import sys, pathlib, shutil, py_compile
site, stamp = pathlib.Path(sys.argv[1]), sys.argv[2]
MARK = "_kc_multi_admin_v1"
PREREQ = "_kc_member_no_escalation_v1"
C6 = "⛔ Chỉ owner chính dùng được lệnh này."

plans = []  # (path, new_text) — computed for all files first, written only if all anchors hold


def fail(msg):
    print(f"Set N1: {msg} — CHECK ANCHORS")
    sys.exit(1)


def once(rel, s, old):
    n = s.count(old)
    if n != 1:
        fail(f"{rel} anchor count={n} for {old[:70]!r}")
    return n


def read(rel):
    return (site / rel).read_text(encoding="utf-8")


def plan(rel, edits, tail="", needs=()):
    s = read(rel)
    if MARK in s:
        print(f"Set N1: {rel} already applied — no-op")
        return
    for n in needs:
        if n not in s:
            print(f"Set N1: FAIL — {rel} lacks {n}; apply prerequisite Sets first")
            sys.exit(1)
    for old, new in edits:
        once(rel, s, old)
        s = s.replace(old, new)
    plans.append((site / rel, s + tail))


# ------------------------------------------------ 1. is_owner (access.py)
plan(
    "slack/handler_runtime/access.py",
    [(
        'def is_owner(user_id: str) -> bool:\n'
        '    """Check if *user_id* is the primary owner (with W/U prefix cross-match)."""\n'
        '    if not _owner_id or not user_id:\n'
        '        return False\n'
        '    if user_id == _owner_id:\n'
        '        return True\n'
        '    return user_id.replace("W", "U", 1) == _owner_id or user_id.replace("U", "W", 1) == _owner_id\n',

        'def is_owner(user_id: str, *, primary: bool = False) -> bool:\n'
        '    """Check if *user_id* is the owner (with W/U prefix cross-match).\n'
        '\n'
        '    An admin listed in ``KIROCREW_ADMIN_USER_IDS`` (comma separated, read on every\n'
        '    call) counts as the owner too, unless *primary* is True: that matches the\n'
        '    configured primary owner only. With no owner configured nobody is an owner.\n'
        '    """\n'
        f'    # Set N1 ({MARK}). Inline on purpose: this function runs on the handler\n'
        '    # module globals after composition, so a new top-level helper here would NameError.\n'
        '    if not _owner_id or not user_id:\n'
        '        return False\n'
        '    if user_id == _owner_id:\n'
        '        return True\n'
        '    if user_id.replace("W", "U", 1) == _owner_id or user_id.replace("U", "W", 1) == _owner_id:\n'
        '        return True\n'
        '    if primary:\n'
        '        return False\n'
        '    import os\n'
        '\n'
        '    for _kc_admin in os.environ.get("KIROCREW_ADMIN_USER_IDS", "").split(","):\n'
        '        _kc_admin = _kc_admin.strip()\n'
        '        if _kc_admin and (\n'
        '            user_id == _kc_admin\n'
        '            or user_id.replace("W", "U", 1) == _kc_admin\n'
        '            or user_id.replace("U", "W", 1) == _kc_admin\n'
        '        ):\n'
        '            return True\n'
        '    return False\n',
    )],
)

# ------------------------------------------------ 2. transport.py
plan(
    "slack/transport.py",
    [
        (
            "        return bool(conversation_id and principal and principal in self._allowed_users)\n",
            "        return bool(\n"
            "            conversation_id\n"
            "            and principal\n"
            f"            and (principal in self._allowed_users or _kc_admin_ok(principal))  # Set N1 ({MARK})\n"
            "        )\n",
        ),
        (
            "        allowed = bool(msg.user_id) and msg.user_id in self._allowed_users\n",
            "        allowed = bool(msg.user_id) and (\n"
            f"            msg.user_id in self._allowed_users or _kc_admin_ok(msg.user_id)  # Set N1 ({MARK})\n"
            "        )\n",
        ),
    ],
    tail=(
        "\n\n"
        f"def _kc_admin_ok(user_id: str) -> bool:\n"
        f'    """Set N1 ({MARK}): True for an admin or the owner (KIROCREW_ADMIN_USER_IDS).\n'
        "\n"
        "    Admins are not stored in the allowlist, because the dashboard writes replace that\n"
        "    set; the check is made here on every call instead.\n"
        '    """\n'
        "    if not user_id:\n"
        "        return False\n"
        "    from kiro_crew.slack.handler import is_owner\n"
        "\n"
        "    return bool(is_owner(user_id))\n"
    ),
)

denied_sel = (
    "{ind}sel().log_api_access(\n"
    "{ind}    caller={caller},\n"
    '{ind}    operation="slack.yolo",\n'
    '{ind}    outcome="denied",\n'
    '{ind}    source="slack",\n'
    '{ind}    error="primary owner only (Set N1)",\n'
    "{ind})\n"
)

# ------------------------------------------------ 3. linked slot (one of three files)
# An admin is DROPPED here (return True): callers go on with the turn only on False, and a
# linked thread resolves to the dashboard session key, so False would let the admin drive the
# owner's dashboard conversation. A member keeps the Set O3 fall-through (read-only by Set O2).
SLOT_OLD = (
    '    if is_allowed_user(user_id) and not is_owner(user_id):\n'
    '        logger.info("Set O3: member %s not routed into linked slot", user_id)\n'
    '        return False\n'
)
SLOT_NEW = (
    f'    # Set N1 ({MARK}): neither an admin nor a member is routed into a linked dashboard slot.\n'
    '    if is_allowed_user(user_id) and not is_owner(user_id, primary=True):\n'
    '        if is_owner(user_id):\n'
    '            logger.info("Set N1: admin %s dropped in linked thread (primary owner only)", user_id)\n'
    + denied_sel.format(ind="            ", caller="user_id").replace('"slack.yolo"', '"slack.linked_thread"')
    + '            try:\n'
    f'                await slack.post_message(channel, "{C6}", reply_ts)\n'
    '            except Exception:\n'
    '                logger.debug("Set N1: linked-thread notice failed", exc_info=True)\n'
    '            return True\n'
    '        logger.info("Set O3: member %s not routed into linked slot", user_id)\n'
    '        return False\n'
)
slot_files = [
    rel for rel in ("slack/handler.py", "slack/handler_runtime/inbound.py", "slack/handler_runtime/dispatch.py")
    if (site / rel).exists() and (SLOT_OLD in read(rel) or (MARK in read(rel) and "Set N1: admin %s dropped" in read(rel)))
]
if len(slot_files) != 1:
    fail(f"linked-slot anchor found in {len(slot_files)} files ({slot_files})")
plan(slot_files[0], [(SLOT_OLD, SLOT_NEW)], needs=(PREREQ,))

# ------------------------------------------------ 4. /kirocrew yolo (events.py)
plan(
    "slack/events.py",
    [(
        "    arg = args.strip().lower()\n",
        "    arg = args.strip().lower()\n"
        f"    # Set N1 ({MARK}): an admin may turn YOLO off, but not on or renew it.\n"
        '    if arg in ("on", "renew") and not is_owner(caller_id, primary=True):\n'
        + denied_sel.format(ind="        ", caller="caller_id")
        + f'        await respond("{C6}")\n'
        "        return\n",
    )],
)

# ------------------------------------------------ 5/6. !yolo and !link-to-dashboard (commands.py)
rel = "slack/handler_runtime/commands.py"
cs = read(rel)
if MARK in cs:
    print(f"Set N1: {rel} already applied — no-op")
else:
    yolo_old = "    yolo_active = is_yolo_mode()\n"
    once(rel, cs, yolo_old)
    cs = cs.replace(
        yolo_old,
        yolo_old
        + f"    # Set N1 ({MARK}): an admin may turn YOLO off, but not on or renew it.\n"
        '    if len(parts) >= 2 and parts[1].lower() in ("on", "renew") and not is_owner(user_id, primary=True):\n'
        + denied_sel.format(ind="        ", caller="user_id")
        + f'        await slack.post_message(channel, "{C6}", reply_ts)\n'
        '        return ""\n',
    )
    head = "async def _bang_link_to_dashboard("
    once(rel, cs, head)
    at = cs.index(head)
    gate = "    if not is_allowed_user(user_id):\n"
    gi = cs.find(gate, at)
    if gi < 0:
        fail(f"{rel} lacks the allowed-user check in _bang_link_to_dashboard")
    cs = (
        cs[:gi]
        + f"    # Set N1 ({MARK}): linking a thread to the dashboard is for the primary owner only.\n"
        + "    if not is_owner(user_id, primary=True):\n"
        + "        sel().log_api_access(\n"
        + "            caller=user_id,\n"
        + '            operation="slack.link_to_dashboard",\n'
        + '            outcome="denied",\n'
        + '            source="slack",\n'
        + '            error="primary owner only (Set N1)",\n'
        + "        )\n"
        + f'        await slack.post_message(channel, "{C6}", reply_ts)\n'
        + '        return ""\n'
        + cs[gi:]
    )
    plans.append((site / rel, cs))

# ------------------------------------------------ 7. dashboard link (allowlist.py)
plan(
    "slack/allowlist.py",
    [(
        "    session_ttl = min(ttl, MAX_SESSION_TTL_SECS)\n",
        f"    # Set N1 ({MARK}): only the primary owner may mint a dashboard link. One gate for\n"
        "    # /kirocrew dashboard and !dashboard, so the caller reports its usual failure text.\n"
        "    from kiro_crew.slack.handler import is_owner\n"
        "\n"
        "    if not is_owner(user_id, primary=True):\n"
        + denied_sel.format(ind="        ", caller="user_id").replace('"slack.yolo"', '"slack.dashboard_link"')
        + '        return ""\n'
        "    session_ttl = min(ttl, MAX_SESSION_TTL_SECS)\n",
    )],
)

# ------------------------------------------------ 8. "Link to Dashboard" button (interactions.py)
plan(
    "slack/interactions.py",
    [(
        "    if action_id == LINK_DASHBOARD_ACTION:\n"
        '        user_id = payload.get("user", {}).get("id", "")\n',
        "    if action_id == LINK_DASHBOARD_ACTION:\n"
        '        user_id = payload.get("user", {}).get("id", "")\n'
        f"        # Set N1 ({MARK}): the button ends in the same import as !link-to-dashboard, so it is\n"
        "        # for the primary owner only.\n"
        "        if not is_owner(user_id, primary=True):\n"
        + denied_sel.format(ind="            ", caller="user_id").replace('"slack.yolo"', '"slack.link_to_dashboard"')
        + "            if channel and user_id and _orch and _orch.slack:\n"
        "                try:\n"
        f'                    await _orch.slack.post_ephemeral(channel, user_id, "{C6}")\n'
        "                except Exception:\n"
        '                    logger.debug("Set N1 ephemeral failed", exc_info=True)\n'
        "            return\n",
    )],
)

if plans:
    for p, text in plans:
        shutil.copy2(p, p.with_name(p.name + f".bak-setn1-{stamp}"))
        p.write_text(text, encoding="utf-8")
        py_compile.compile(str(p), doraise=True)
        for pyc in (p.parent / "__pycache__").glob(p.stem + ".*.pyc"):
            pyc.unlink()
        print(f"Set N1: patched {p.relative_to(site)}")

import importlib
import inspect

H = importlib.import_module("kiro_crew.slack.handler")
T = importlib.import_module("kiro_crew.slack.transport")
assert "primary" in inspect.signature(H.is_owner).parameters
assert hasattr(T, "_kc_admin_ok")
print("Set N1: OK (imports + names verified)")
PY
